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
Bodywork config file reader and parser.
"""
from pathlib import Path
from typing import Dict, Sequence, Union

import yaml

from .exceptions import BodyworkProjectConfigYAMLError

ConfigSection = Dict[str, Union[str, float, int, bool]]
Config = Dict[str, Union[ConfigSection, Sequence[ConfigSection]]]


class BodyworkConfig:
    """Config file handler."""

    def __init__(self, config_file_path: Path):
        """Constructor.

        :param config_file_path: Config file path.
        :raises FileExistsError: if config_file_path does not exist.
        :raises BodyworkProjectConfigYAMLError: if config file cannot be
            parsed as valid YAML.
        """
        try:
            config_yaml =  config_file_path.read_text(encoding='utf-8', errors='strict')
            self.config: Config = yaml.load(config_yaml, Loader=yaml.SafeLoader)
        except (FileNotFoundError, IsADirectoryError):
            raise FileExistsError(f'no config file found at {config_file_path}')
        except yaml.YAMLError as e:
            raise BodyworkProjectConfigYAMLError(config_file_path) from e

    def __getitem__(
        self,
        config_section_key: str
        ) -> Union[ConfigSection, Sequence[ConfigSection]]:
        """Access sections of the config file directly."""
        return self.config[config_section_key]
