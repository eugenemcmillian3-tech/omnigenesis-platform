#!/usr/bin/env python3
"""Interactive CLI Smart Terminal (OmniShell-Ω) for your Sovereign Cloud Computer."""
import sys
import omnigenesis_engine as eng

def main() -> None:
    core = eng.OmniGenesisSingularityCore("OmniShell-Ω Interactive Session")
    core.execute_full_convergence(cycles=1)
    reg = eng.OmniPlatformModelRegistry(core)
    cat = eng.OmniEnterpriseTemplateCatalog()
    cloud = eng.SovereignCloudComputerEngine()
    deployer = eng.AutonomousPaaSSelfDeployer(cloud, core, reg, cat)
    cluster = eng.DistributedCloudClusterMesh(cloud)
    shell = eng.SmartTerminalOrchestrator(cloud, deployer, cluster)

    if len(sys.argv) > 1:
        res = shell.execute_terminal_command(" ".join(sys.argv[1:]))
        print(res["stdout"])
        return

    print("==========================================================================")
    print("  OMNISHELL-Ω v7.0 — SMART ADVANCED TERMINAL & SELF-DEPLOYING CLOUD OS")
    print("  Type 'omni help', 'omni cloud bootstrap --self', or natural language.")
    print("==========================================================================")
    while True:
        try:
            cmd = input("omni@sovereign-cloud:~# ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting OmniShell-Ω.")
            break
        if cmd in ("exit", "quit"):
            break
        res = shell.execute_terminal_command(cmd)
        print(res["stdout"])

if __name__ == "__main__":
    main()
