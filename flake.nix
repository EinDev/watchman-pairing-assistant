{
  description = "GUI for pairing SteamVR Tracking devices using lighthouse_console";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      forAllSystems = f:
        nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (system:
          f (import nixpkgs { inherit system; })
        );
    in
    {
      packages = forAllSystems (pkgs: {
        default = pkgs.callPackage ./nix/package.nix { };
      });

      devShells = forAllSystems (pkgs:
        let
          python = pkgs.python313;
          py = python.pkgs;
          pythonEnv = python.withPackages (ps: with ps; [
            pyusb
            customtkinter
            tkinter
            libusb-package
          ]);
        in
        {
          # Default dev shell: uses nixpkgs Python packages (no pip network access)
          default = pkgs.mkShell {
            packages = [
              pythonEnv
              pkgs.libusb1
              pkgs.tcl
              pkgs.tk
              pkgs.git
            ];
            shellHook = ''
              echo "Nix dev shell ready. Try: python source/main.py"
            '';
          };

          # Optional venv dev shell: installs exact versions from requirements.txt via pip
          venv = pkgs.mkShell {
            packages = [
              python
              py.venvShellHook
              pkgs.libusb1
              pkgs.tcl
              pkgs.tk
              pkgs.git
            ];
            venvDir = ".venv";
            postVenvCreation = ''
              python -m pip install --upgrade pip
              if [ -f requirements.txt ]; then
                pip install -r requirements.txt
              fi
              echo "Virtualenv ready. Activate: source .venv/bin/activate"
            '';
            postShellHook = ''
              source .venv/bin/activate
              echo "Venv activated. Run: python source/main.py"
            '';
          };
        }
      );
    };
}