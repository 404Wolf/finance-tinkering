{
  description = "Financial tinkering :)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        python = pkgs.python3.withPackages (
          ps: with ps; [
            matplotlib
            pandas
            numpy
            scipy
          ]
        );
      in
      {
        devShells = {
          default = pkgs.mkShell {
            UV_VENV_CLEAR = "1";
            shellHook = ''
              uv sync
              uv venv
              source .venv/bin/activate
            '';
            packages = [
              pkgs.typst
              pkgs.ruff
              pkgs.nil
              pkgs.nixd
              pkgs.nixfmt
              pkgs.uv
              pkgs.ruff
              python
            ];
          };
        };
      }
    );
}
