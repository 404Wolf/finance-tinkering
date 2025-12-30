{
  description = "Data Analysis Homework 2";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix.url = "github:numtide/treefmt-nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      treefmt-nix,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        python = pkgs.python3.withPackages (
          ps: with ps; [
            black
            matplotlib
            pandas
            numpy
            scipy
          ]
        );

        treefmtconfig = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs = {
            nixfmt.enable = true;
            yamlfmt.enable = true;
            typstfmt.enable = true;
          };
        };
      in
      {
        formatter = treefmtconfig.config.build.wrapper;

        devShells = {
          default = pkgs.mkShell {
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
