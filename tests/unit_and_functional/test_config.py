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
Test Bodywork config reading, parsing and validation.
"""
from pathlib import Path

from pytest import fixture, raises

from bodywork.config import (
    BodyworkConfig,
    Project,
    BatchStage,
    ServiceStage,
    Stage,
    Logging,
    _parse_dag_definition,
    _check_workflow_stages_are_configured
)
from bodywork.constants import (
    BODYWORK_CONFIG_VERSION,
    BODYWORK_VERSION
)
from bodywork.exceptions import (
    BodyworkConfigMissingSectionError,
    BodyworkConfigVersionMismatchError,
    BodyworkConfigMissingOrInvalidParamError,
    BodyworkConfigParsingError
)


@fixture(scope='function')
def bodywork_config(project_repo_location: Path) -> BodyworkConfig:
    config_file = project_repo_location / 'bodywork.yaml'
    return BodyworkConfig(config_file)


def test_that_invalid_config_file_path_raises_error(
    project_repo_location: Path
):
    bad_config_file = project_repo_location / 'bodywerk.yaml'
    with raises(FileExistsError, match='no config file found'):
        BodyworkConfig(bad_config_file)


def test_that_invalid_config_format_raises_error(
    project_repo_location: Path
):
    config_file = project_repo_location / 'bodywork.ini'
    expected_exception_msg = f'cannot parse YAML from {config_file}'
    with raises(BodyworkConfigParsingError, match=expected_exception_msg):
        BodyworkConfig(config_file)


def test_that_empty_config_file_raises_error(
    project_repo_location: Path
):
    config_file = project_repo_location / 'bodywork_empty.yaml'
    expected_exception_msg = f'cannot parse YAML from {config_file}'
    with raises(BodyworkConfigParsingError, match=expected_exception_msg):
        BodyworkConfig(config_file)


def test_that_config_file_with_missing_sections_raises_error(
    bodywork_config: BodyworkConfig
):
    del bodywork_config._config['version']
    del bodywork_config._config['project']
    del bodywork_config._config['stages']
    del bodywork_config._config['logging']
    expected_exception_msg = 'missing sections: version, project, stages, logging'
    with raises(BodyworkConfigMissingSectionError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_that_config_file_with_invalid_schema_version_raises_error(
    bodywork_config: BodyworkConfig
):
    bodywork_config._config['version'] = 'not the version'
    expected_exception_msg = 'missing or invalid parameters: version'
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()

    bodywork_config._config['version'] = '1.0.0'
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_that_config_file_with_mismatched_schema_version_raises_error(
    bodywork_config: BodyworkConfig
):
    bodywork_config._config['version'] = '0.1'
    expected_exception_msg = (f'config file has schema version 0.1, when Bodywork '
                              f'version {BODYWORK_VERSION} requires schema version '
                              f'{BODYWORK_CONFIG_VERSION}')
    with raises(BodyworkConfigVersionMismatchError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_that_config_file_with_non_list_stages_raises_error(
    bodywork_config: BodyworkConfig
):
    bodywork_config._config['stages'] = 'bad'
    expected_exception_msg = (
        'missing or invalid parameters: '
        'project.workflow - cannot find valid stage @ stages.stage_1, '
        'project.workflow - cannot find valid stage @ stages.stage_2, '
        'project.workflow - cannot find valid stage @ stages.stage_3, '
        'stages._ - no stage configs provided'
    )
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_bodywork_config_project_section_validation():
    config_missing_all_params = {'not_a_valid_section': None}
    expected_exception_msg = ('missing or invalid parameters: project.name, '
                              'project.docker_image, project.DAG')
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        Project(config_missing_all_params)

    config_all_invalid_params = {'name': -1, 'docker_image': [], 'DAG': None}
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        Project(config_all_invalid_params)

    config_invalid_DAG = {'name': 'me', 'docker_image': 'my/img:1.0', 'DAG': 'a>>b,>>c'}
    expected_exception_msg = ('missing or invalid parameters: project.DAG -> '
                              'null stages found in step 2 when parsing DAG')
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        Project(config_invalid_DAG)

    config_all_valid_params = {'name': 'me', 'docker_image': 'my/img:1.0', 'DAG': 'a>>b'}
    try:
        Project(config_all_valid_params)
        assert True
    except Exception:
        assert False


def test_bodywork_config_logging_section_validation():
    config_missing_all_params = {'not_a_valid_section': None}
    expected_exception_msg = 'missing or invalid parameters: logging.log_level'
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        Logging(config_missing_all_params)

    config_all_params = {'log_level': 'INFO'}
    try:
        Logging(config_all_params)
        assert True
    except Exception:
        assert False


def test_bodywork_config_generic_stage_validation():
    stage_name = 'my_stage'
    root_dir = Path('.')

    config_missing_all_params = {'not_a_valid_section': None}
    expected_missing_or_invalid_param = [
        'stages.my_stage.executable_module',
        'stages.my_stage.cpu_request',
        'stages.my_stage.memory_request_mb'
    ]
    stage = Stage(stage_name, config_missing_all_params, root_dir)
    assert stage._missing_or_invalid_param == expected_missing_or_invalid_param

    config_missing_all_invalid_params = {
        'executable_module': None,
        'cpu_request': None,
        'memory_request_mb': None,
        'requirements': None,
        'secrets': None
    }
    expected_missing_or_invalid_param = [
        'stages.my_stage.executable_module',
        'stages.my_stage.cpu_request',
        'stages.my_stage.memory_request_mb',
        'stages.my_stage.requirements',
        'stages.my_stage.secrets'
    ]
    stage = Stage(stage_name, config_missing_all_invalid_params, root_dir)
    assert stage._missing_or_invalid_param == expected_missing_or_invalid_param

    config_all_valid_params = {
        'executable_module': 'main.py',
        'cpu_request': 0.5,
        'memory_request_mb': 100,
        'requirements': ['foo==1.0.0', 'bar==2.0'],
        'secrets': {'FOO_UN': 'secret-bar', 'FOO_PWD': 'secret-bar'}
    }
    expected_missing_or_invalid_param = []
    stage = Stage(stage_name, config_all_valid_params, root_dir)
    assert stage._missing_or_invalid_param == expected_missing_or_invalid_param

    config_all_valid_params_no_secrets_requirements = {
        'executable_module': 'main.py',
        'cpu_request': 0.5,
        'memory_request_mb': 100
    }
    expected_missing_or_invalid_param = []
    stage = Stage(stage_name, config_all_valid_params_no_secrets_requirements, root_dir)
    assert stage._missing_or_invalid_param == expected_missing_or_invalid_param


def test_stage_equality_operations():
    root_dir = Path('.')
    generic_stage_config = {
        'executable_module': 'main.py',
        'cpu_request': 0.5,
        'memory_request_mb': 100,
        'requirements': ['foo==1.0.0', 'bar==2.0'],
        'secrets': {'FOO_UN': 'secret-bar', 'FOO_PWD': 'secret-bar'}
    }
    stage_1 = Stage('stage_1', generic_stage_config, root_dir)
    stage_2 = Stage('stage_2', generic_stage_config, root_dir)
    assert stage_1 == stage_1
    assert stage_1 != stage_2


def test_bodywork_config_batch_stage_validation():
    root_dir = Path('.')
    stage_name = 'my_stage'

    valid_generic_stage_config = {
        'executable_module': 'main.py',
        'cpu_request': 0.5,
        'memory_request_mb': 100,
        'requirements': ['foo==1.0.0', 'bar==2.0'],
        'secrets': {'FOO_UN': 'secret-bar', 'FOO_PWD': 'secret-bar'}
    }

    config_missing_all_params = {'not_a_valid_section': None}
    expected_exception_msg = (
        'missing or invalid parameters: '
        'stages.my_stage.batch.max_completion_time_seconds, '
        'stages.my_stage.batch.retries'
    )
    full_config = {**valid_generic_stage_config, 'batch': config_missing_all_params}
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        BatchStage(stage_name, full_config, root_dir)

    config_all_invalid_params = {
        'max_completion_time_seconds': -1,
        'retries': -1
    }
    expected_exception_msg = (
        'missing or invalid parameters: '
        'stages.my_stage.batch.max_completion_time_seconds, '
        'stages.my_stage.batch.retries'
    )
    full_config = {**valid_generic_stage_config, 'batch': config_all_invalid_params}
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        BatchStage(stage_name, full_config, root_dir)

    config_all_valid_params = {
        'max_completion_time_seconds': 10,
        'retries': 1
    }
    full_config = {**valid_generic_stage_config, 'batch': config_all_valid_params}
    stage = BatchStage(stage_name, full_config, root_dir)
    assert stage._missing_or_invalid_param == []


def test_bodywork_config_service_stage_validation():
    root_dir = Path('.')
    stage_name = 'my_stage'

    valid_generic_stage_config = {
        'executable_module': 'main.py',
        'cpu_request': 0.5,
        'memory_request_mb': 100,
        'requirements': ['foo==1.0.0', 'bar==2.0'],
        'secrets': {'FOO_UN': 'secret-bar', 'FOO_PWD': 'secret-bar'}
    }

    config_missing_all_params = {'not_a_valid_section': None}
    expected_exception_msg = (
        'missing or invalid parameters: '
        'stages.my_stage.service.max_startup_time_seconds, '
        'stages.my_stage.service.replicas, '
        'stages.my_stage.service.port, '
        'stages.my_stage.service.ingress'
    )
    full_config = {**valid_generic_stage_config, 'service': config_missing_all_params}
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        ServiceStage(stage_name, full_config, root_dir)

    config_all_invalid_params = {
        'max_startup_time_seconds': -1,
        'replicas': -1,
        'port': -1,
        'ingress': 'no'
    }
    expected_exception_msg = (
        'missing or invalid parameters: '
        'stages.my_stage.service.max_startup_time_seconds, '
        'stages.my_stage.service.replicas, '
        'stages.my_stage.service.port, '
        'stages.my_stage.service.ingress'
    )
    full_config = {**valid_generic_stage_config, 'service': config_all_invalid_params}
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        ServiceStage(stage_name, full_config, root_dir)

    config_all_valid_params = {
        'max_startup_time_seconds': 10,
        'replicas': 2,
        'port': 5000,
        'ingress': True
    }
    full_config = {**valid_generic_stage_config, 'service': config_all_valid_params}
    stage = ServiceStage(stage_name, full_config, root_dir)
    assert stage._missing_or_invalid_param == []


def test_py_modules_that_cannot_be_located_raise_error(
    bodywork_config: BodyworkConfig
):
    bodywork_config.check_py_modules_exist = True
    try:
        bodywork_config._validate_parsed_config()
        assert True
    except Exception:
        assert False

    stage_1 = bodywork_config._config['stages']['stage_1']
    bodywork_config._config['stages']['stage_one'] = stage_1
    del bodywork_config._config['stages']['stage_1']
    stage_2 = bodywork_config._config['stages']['stage_2']
    bodywork_config._config['stages']['stage_two'] = stage_2
    del bodywork_config._config['stages']['stage_2']
    bodywork_config._config['stages']['stage_3']['executable_module'] = 'i_dont_exist.py'
    expected_exception_msg = (
        'missing or invalid parameters: '
        'project.workflow - cannot find valid stage @ stages.stage_1, '
        'project.workflow - cannot find valid stage @ stages.stage_2, '
        'stages.stage_3.executable_module -> cannot locate file, '
        'stages.stage_one -> cannot locate dir, '
        'stages.stage_two -> cannot locate dir'
    )
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_that_subsection_validation_feeds_through_to_validation_report(
    bodywork_config: BodyworkConfig
):
    del bodywork_config._config['project']['docker_image']
    del bodywork_config._config['logging']['log_level']
    del bodywork_config._config['stages']['stage_1']['batch']
    bodywork_config._config['stages']['stage_2']['service'] = {'foo': 'bar'}
    expected_exception_msg = (
        'missing or invalid parameters: '
        'logging.log_level, '
        'project.docker_image, '
        'project.workflow - cannot find valid stage @ stages.stage_1, '
        'project.workflow - cannot find valid stage @ stages.stage_2, '
        'stages.stage_1.batch/service, '
        'stages.stage_2.batch/service'
    )
    with raises(BodyworkConfigMissingOrInvalidParamError, match=expected_exception_msg):
        bodywork_config._validate_parsed_config()


def test_that_config_values_can_be_retreived_from_valid_config(
    bodywork_config: BodyworkConfig
):
    config = bodywork_config
    assert config.project.name == 'bodywork-test-project'
    assert config.logging.log_level == 'INFO'
    assert len(config.stages) == 3

    assert 'stage_1' in config.stages
    assert config.stages['stage_1'].executable_module == 'main.py'
    assert config.stages['stage_1'].max_completion_time == 60
    assert config.stages['stage_1'].retries == 4
    assert config.stages['stage_1'].env_vars_from_secrets[0] == ('foobar-secret', 'FOO')
    assert config.stages['stage_1'].requirements == ['numpy==1.19.1']

    assert 'stage_3' in config.stages
    assert config.stages['stage_3'].executable_module == 'main.py'
    assert config.stages['stage_3'].max_startup_time == 60
    assert config.stages['stage_3'].replicas == 2
    assert config.stages['stage_3'].port == 5000
    assert config.stages['stage_3'].create_ingress is True
    assert config.stages['stage_3'].env_vars_from_secrets[1] == ('foobar-secret', 'BAR')
    assert config.stages['stage_3'].requirements == ['wheel==0.34.2']


def test_parse_dag_definition_parses_multi_stage_dags():
    dag_definition = 'stage_1 >> stage_2,stage_3 >> stage_4'
    parsed_dag_structure = _parse_dag_definition(dag_definition)
    expected_dag_structure = [
        ['stage_1'],
        ['stage_2', 'stage_3'],
        ['stage_4']
    ]
    assert parsed_dag_structure == expected_dag_structure


def test_parse_dag_definition_parses_single_stage_dags():
    dag_definition = 'stage_1'
    parsed_dag_structure = _parse_dag_definition(dag_definition)
    expected_dag_structure = [['stage_1']]
    assert parsed_dag_structure == expected_dag_structure


def test_parse_dag_definition_raises_invalid_dag_definition_exceptions():
    dag_definition = 'stage_1 >> ,stage_3 >> stage_4'
    with raises(ValueError, match='null stages found in step 2'):
        _parse_dag_definition(dag_definition)


def test_check_workflow_stages_are_configured():
    workflow = [['a'], ['b', 'c'], ['d']]
    configured_stages = ['a', 'b', 'd']
    missing_stage_configs = _check_workflow_stages_are_configured(
        workflow,
        configured_stages
    )
    assert missing_stage_configs == [
        'project.workflow - cannot find valid stage @ stages.c'
    ]
    assert _check_workflow_stages_are_configured(['a'], ['a']) == []
