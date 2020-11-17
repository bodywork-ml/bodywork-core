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
