# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2021  Bodywork Machine Learning Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Bodywork config file reader and parser. Works for both project and stage
config files.
"""
from configparser import ConfigParser, ExtendedInterpolation, SectionProxy
from pathlib import Path


class BodyworkConfig:
    """Config file handler."""

    def __init__(self, config_file_path: Path):
        """Constructor.

        :param config_file_path: Config file path.
        :raises RuntimeError: if config_file_path does not exist.
        """
        if not config_file_path.exists() or config_file_path.is_dir():
            raise FileExistsError(f'no config file found at {config_file_path}')
        config_parser = ConfigParser(interpolation=ExtendedInterpolation())
        config_parser.read(config_file_path)
        self.config_parser = config_parser

    def __getitem__(self, config_section_key: str) -> SectionProxy:
        """Access sections of the config file directly."""
        return self.config_parser[config_section_key]
