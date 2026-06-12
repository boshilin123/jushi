import subprocess


def run_command(args: list[str], timeout: int = 30) -> str:
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout
