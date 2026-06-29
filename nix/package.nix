{ lib,
  makeDesktopItem,
  python3,
  python3Packages,
  libusb1,
  tcl,
  tk
}:

python3Packages.buildPythonApplication {
  pname = "watchman-pairing-assistant";
  version = "2.2.1";
  pyproject = true;
  src = ../.;

  # Python deps resolved via nixpkgs so imports work at runtime
  build-system = with python3Packages; [ setuptools ];
  dependencies = with python3Packages; [
    pyusb
    customtkinter
    tkinter
    libusb-package
  ];

  buildInputs = [
    libusb1
    tcl
    tk
  ];

  # Fail early if deps aren’t resolvable on this nixpkgs
  pythonImportsCheck = [
    "customtkinter"
    "usb"
    "libusb_package"
  ];

  meta = {
    homepage = "https://github.com/TayouVR/watchman-pairing-assistant";
    downloadPage = "https://github.com/TayouVR/watchman-pairing-assistant/releases";
    description = "GUI for pairing SteamVR Tracking devices using lighthouse_console";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [
      {
        name = "Tayou";
        email = "nix-maintainer@tayou.org";
        github = "TayouVR";
        githubId = 31988415;
      }
    ];
    platforms = lib.platforms.linux;
  };
}
