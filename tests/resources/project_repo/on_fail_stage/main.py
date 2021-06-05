"""
This module contains dummy code meant to represent a Bodywork project
stage, for use with testing.
"""


def main() -> None:
    print('foo')
    with open("../../bodywork_project_output/on_fail_stage_test_file.txt", "w") as f:
        f.write("Hello from on fail stage\n")


if __name__ == "__main__":
    main()
