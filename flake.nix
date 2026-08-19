{
  description = "Portable numeric-weight Goku terminal font collection";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in {
      devShells = forAllSystems (system:
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
        in {
          default = pkgs.mkShell {
            packages = with pkgs; [
              # Keep the build interpreter first: changing Python versions can
              # change serialized sfnt bytes even when geometry is identical.
              buildPython
              qualityPython
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

            shellHook = ''
              echo "Goku build shell"
              echo "Run: make all"
            '';
          };
        });
    };
}
