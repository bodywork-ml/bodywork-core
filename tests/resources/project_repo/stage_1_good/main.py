"""
This module contains dummy code meant to represent a Bodywork project
stage, for use with testing.
"""
import numpy


def main() -> None:
    count_to_ten = numpy.sum(numpy.ones(10))
    with open('bodywork_project_output/stage_1_test_file.txt', 'w') as f:
        f.write('Hello from stage 1\n')
        f.write(f'numpy.sum(numpy.ones(10))={count_to_ten}')


if __name__ == '__main__':
    main()
