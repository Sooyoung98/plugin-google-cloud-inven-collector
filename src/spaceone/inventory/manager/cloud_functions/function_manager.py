import time
import logging
from datetime import datetime, timedelta
import pytz

from spaceone.inventory.libs.manager import GoogleCloudManager
from spaceone.inventory.libs.schema.base import ReferenceModel
from spaceone.inventory.connector.cloud_functions.function import FunctionConnector
from spaceone.inventory.model.cloud_functions.function.cloud_service_type import CLOUD_SERVICE_TYPES, cst_function
from spaceone.inventory.model.cloud_functions.function.cloud_service import FunctionResource, FunctionResponse
from spaceone.inventory.model.cloud_functions.function.data import Function

_LOGGER = logging.getLogger(__name__)


class FunctionManager(GoogleCloudManager):
    connector_name = 'FunctionConnector'
    cloud_service_types = CLOUD_SERVICE_TYPES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cloud_service_group = cst_function.group
        self.cloud_service_type = cst_function.name
        self.function_conn = None

    def collect_cloud_service(self, params):
        """
        Args:
            params:
                - options
                - schema
                - secret_data
                - filter
                - zones
        Response:
            CloudServiceResponse/ErrorResourceResponse
        """
        _LOGGER.debug(f'** [{self.cloud_service_group}] {self.cloud_service_type} START **')

        start_time = time.time()

        collected_cloud_services = []
        error_responses = []
        function_id = ""

        secret_data = params['secret_data']
        project_id = secret_data['project_id']

        self.function_conn: FunctionConnector = self.locator.get_connector(self.connector_name, **params)

        ##################################
        # 0. Gather All Related Resources
        # List all information through connector
        ##################################
        functions = self.function_conn.list_functions()

        for function in functions:
            print(function)
            try:
                ##################################
                # 1. Set Basic Information
                ##################################
                function_name = function.get('name')
                location, function_id = self._make_location_and_id(function_name, project_id)
                labels = function.get('labels')

                ##################################
                # 2. Make Base Data
                ##################################
                display = {
                    'environment': self._make_readable_environment(function['environment']),
                    'function_id': function_id,
                    'last_deployed': self._make_last_deployed(function['updateTime']),
                    'region': location
                }
                print(display)
                ##################################
                # 3. Make function data
                ##################################
                function.update({
                    # 'function_id': function_id,
                    'project': project_id,
                    'display': display
                })
                function_data = Function(function, strict=False)

                ##################################
                # 4. Make Function Resource Code
                ##################################
                function_resource = FunctionResource({
                    'name': function_name,
                    'account': project_id,
                    'tags': labels,
                    'region_code': location,
                    'instance_type': '',
                    'instance_size': 0,
                    'data': function_data,
                    'reference': ReferenceModel(function_data.reference())
                })
                self.set_region_code(location)
                ##################################
                # 5. Make Resource Response Object
                ##################################
                collected_cloud_services.append(FunctionResponse({'resource': function_resource}))
                print()
            except Exception as e:
                _LOGGER.error(f'[collect_cloud_service] => {e}', exc_info=True)
                error_response = self.generate_resource_error_response(e, self.cloud_service_group,
                                                                       self.cloud_service_type, function_id)
                error_responses.append(error_response)

        _LOGGER.debug(f'** Function Gen1 Finished {time.time() - start_time} Seconds **')
        return collected_cloud_services, error_responses

    @staticmethod
    def _make_location_and_id(function_name, project_id):
        project_path, location_and_id_path = function_name.split(f'projects/{project_id}/locations/')
        location, function, function_id = location_and_id_path.split('/')
        return location, function_id

    @staticmethod
    def _make_readable_environment(environment):
        environment_map = {
            'GEN_1': '1st gen',
            'GEN_2': '2nd gen',
            'ENVIRONMENT_UNSPECIFIED': 'unspecified'
        }
        return environment_map[environment]

    @staticmethod
    def _make_last_deployed(update_time):
        update_time, microseconds = update_time.split('.')
        updated_time = datetime.strptime(update_time, '%Y-%m-%dT%H:%M:%S')
        korea_time = updated_time + timedelta(hours=9)
        return korea_time.strftime("%m/%d, %Y,%I:%M:%S %p")
