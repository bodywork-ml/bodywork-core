"""
This module contains dummy code meant to represent a Bodywork project
stage, for use with testing.
"""
import sys


def main() -> None:
    with open("../../bodywork_project_output/stage_3_test_file.txt", "w") as f:
        try:
            f.write(f"arg1 = {sys.argv[1]}\n")
            f.write(f"arg2 = {sys.argv[2]}\n")
        except Exception:
            f.write("Hello from stage 3\n")


if __name__ == "__main__":
    main()
