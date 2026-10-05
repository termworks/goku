{
  description = "Portable numeric-weight Goku terminal font collection";

  nixConfig = {
    extra-substituters = [ "https://termworks.cachix.org" ];
    extra-trusted-public-keys = [ "termworks.cachix.org-1:Ty7sSVALfD5ajbcWBIdaNHcaEx3fEmVrOo+rSzy0mvE=" ];
  };

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.gohufont = {
    url = "github:hchargois/gohufont/cc36b8c9fed7141763e55dcee0a97abffcf08224";
    flake = false;
  };

  outputs = { self, nixpkgs, gohufont }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      environments = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          # These two FontBakery dependencies accidentally run CPython's own
          # stdlib unittest suite in the pinned Nixpkgs revision. Disable only
          # those broken package-build checks; Goku's FontBakery checks still
          # run in full through the quality target.
          buildPython = pkgs.python3.withPackages (ps: with ps; [
            fonttools
            pillow
            skia-pathops
          ]);
          qualityPythonInterpreter = pkgs.python313.override {
            packageOverrides = final: prev: {
              collidoscope = prev.collidoscope.overridePythonAttrs (_: {
                doCheck = false;
              });
              opentypespec = prev.opentypespec.overridePythonAttrs (_: {
                doCheck = false;
              });
            };
          };
          qualityPython = qualityPythonInterpreter.withPackages (ps: with ps; [
            fontbakery
          ]);
          buildTools = with pkgs; [
            buildPython
            fontforge
            nerd-font-patcher
            fontconfig
            freetype
            harfbuzz
            imagemagick
            librsvg
            opentype-sanitizer
            ttfautohint
          ];
          versionLine = pkgs.lib.findFirst
            (line: pkgs.lib.hasPrefix "VERSION = " line)
            (throw "src/design.py is missing VERSION")
            (pkgs.lib.splitString "\n" (builtins.readFile ./src/design.py));
        in {
          package = pkgs.stdenvNoCC.mkDerivation {
            pname = "goku";
            version = builtins.fromJSON (pkgs.lib.removePrefix "VERSION = " versionLine);
            src = pkgs.lib.cleanSourceWith {
              src = self;
              filter = path: _type:
                !(builtins.elem (baseNameOf path) [ "build" "dist" "result" ".direnv" "vendor" ]);
            };
            nativeBuildInputs = buildTools;
            postPatch = ''
              mkdir -p vendor/gohufont
              cp ${gohufont}/gohufont-uni-14.bdf ${gohufont}/gohufont-uni-14b.bdf \
                ${gohufont}/COPYING-LICENSE vendor/gohufont/
            '';
            buildPhase = ''
              runHook preBuild
              export HOME="$TMPDIR/home"
              mkdir -p "$HOME"
              make release
              runHook postBuild
            '';
            installPhase = ''
              runHook preInstall
              make nix-install NIX_FONT_OUTPUT="$out"
              runHook postInstall
            '';
            doInstallCheck = true;
            installCheckPhase = ''
              runHook preInstallCheck
              make nix-install-check NIX_FONT_OUTPUT="$out"
              runHook postInstallCheck
            '';
            meta = {
              description = "Goku terminal font collection with 18 numeric-weight faces";
              homepage = "https://github.com/termworks/goku";
              platforms = supportedSystems;
            };
          };
          shell = pkgs.mkShell {
            packages = buildTools ++ [ qualityPython ];

            shellHook = ''
              echo "Goku build shell"
              echo "Run: make all"
            '';
          };
        });
    in {
      packages = forAllSystems (system: {
        default = environments.${system}.package;
        goku = environments.${system}.package;
      });
      checks = forAllSystems (system: {
        goku = environments.${system}.package;
      });
      devShells = forAllSystems (system: {
        default = environments.${system}.shell;
      });
    };
}
