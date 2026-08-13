{
  pkgs,
  lib,
  config,
  ...
}:
{
  packages = [
    pkgs.git
    pkgs.git-absorb
    pkgs.sops
    pkgs.age
    pkgs.nodejs
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
    uv.sync.enable = true;
    # backend-grpc and backend-wamp declare conflicting labgrid version
    # ranges (see [tool.uv] conflicts in pyproject.toml), so a bare
    # `uv sync` can no longer resolve -- it would need both at once. Pick
    # one backend as the default for automatic shell-activation sync; switch
    # to the other manually the same way `make test`/`make type-check` do:
    #   uv sync --package labgrid-toolkit-core \
    #           --package labgrid-prometheus-exporter \
    #           --package labgrid-toolkit-backend-wamp
    uv.sync.arguments = [
      "--package"
      "labgrid-toolkit-core"
      "--package"
      "labgrid-prometheus-exporter"
      "--package"
      "labgrid-toolkit-backend-grpc"
    ];
  };

  dotenv.disableHint = true;

  # See full reference at https://devenv.sh/reference/options/
}
