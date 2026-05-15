{ pkgs, lib, config, inputs, ... }:

{
  languages.python.enable = true;
  languages.python.venv.enable = true;

  packages = [
    pkgs.zlib
    pkgs.libGL
    pkgs.glib
    pkgs.xorg.libxcb      # Adds libxcb.so.1
    pkgs.xorg.libX11      # Common follow-up requirement
    pkgs.stdenv.cc.cc.lib
  ];

  env.LD_LIBRARY_PATH = "${lib.makeLibraryPath (with pkgs; [
    stdenv.cc.cc.lib
    zlib
    libGL
    glib
    xorg.libxcb
    xorg.libX11
  ])}";
}
