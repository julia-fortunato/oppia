from __future__ import annotations
import logging
from unittest import mock
from core import feconf
from core.constants import constants
from core.domain import collection_domain
from core.domain import collection_services
from core.domain import exp_domain
from core.domain import exp_fetchers
from core.domain import exp_services
from core.domain import learner_progress_services
from core.domain import param_domain
from core.domain import platform_parameter_list
from core.domain import question_services
from core.domain import recommendations_services
from core.domain import rights_manager
from core.domain import skill_services
from core.domain import stats_domain
from core.domain import stats_services
from core.domain import story_domain
from core.domain import story_fetchers
from core.domain import story_services
from core.domain import taskqueue_services
from core.domain import topic_domain
from core.domain import topic_fetchers
from core.domain import topic_services
from core.domain import translation_domain
from core.domain import user_services
from core.domain import event_services
from core.platform import models
from core.tests import test_utils
from core.controllers import base
from core.controllers import acl_decorators
from core.controllers import domain_objects_validator
from core.controllers import editor
from typing import Dict, Final, List, Optional, Union, TypedDict


def _get_change_list(
    state_name: str,
    property_name: str,
    new_value: Union[bool, str]
) -> List[exp_domain.ExplorationChange]:
    """Generates a change list for a single state change."""
    return [exp_domain.ExplorationChange({
        'cmd': exp_domain.CMD_EDIT_STATE_PROPERTY,
        'state_name': state_name,
        'property_name': property_name,
        'new_value': new_value
    })]

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import exp_models
    from mypy_imports import stats_models
    from mypy_imports import translation_models

(
    exp_models,
    stats_models,
    translation_models
) = models.Registry.import_models([
    models.Names.EXPLORATION,
    models.Names.STATISTICS,
    models.Names.TRANSLATION
])



class ExplorationMaybeLeaveHandlerTest(test_utils.GenericTestBase):
    """Test suite for the ExplorationMaybeLeaveHandler."""

    def setUp(self):
        super(ExplorationMaybeLeaveHandlerTest, self).setUp()
        self.exploration_id = '0'
        self.user_id = 'valid_user'
        self.collection_id = 'valid_collection'
        self.story_id = 'valid_story'
        self.state_name = 'Introduction'
        self.version = 1
        self.session_id = 'session_123'
        self.client_time_spent_in_secs = 10.5
        self.params = {'key1': 'value1'}

        self.swap(
            base.BaseHandler, 
            'REQUIRE_PAYLOAD_CSRF_CHECK', 
            False
        )
        self.signup(self.VIEWER_EMAIL, self.VIEWER_USERNAME)
        self.login(self.VIEWER_EMAIL)
        
    def test_user_id_and_collection_id_valid(self):
        """CT1: user_id and collection_id are valid."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch.object(
            learner_progress_services,
            'mark_collection_as_incomplete',
            autospec=True
        ) as mock_mark_collection:
            self.post_json(
                '/explorehandler/maybe_leave/%s' % self.exploration_id,
                {
                    'version': self.version,
                    'state_name': self.state_name,
                    'collection_id': self.collection_id,
                    'session_id': self.session_id,
                    'client_time_spent_in_secs': self.client_time_spent_in_secs,
                    'params': self.params
                },
                csrf_token
            )
            mock_mark_collection.assert_called_once_with(
                self.user_id, self.collection_id
            )

    def test_collection_id_invalid(self):
        """CT2: collection_id is invalid."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch.object(
            learner_progress_services,
            'mark_collection_as_incomplete',
            autospec=True
        ) as mock_mark_collection:
            self.post_json(
                '/explorehandler/maybe_leave/%s' % self.exploration_id,
                {
                    'version': self.version,
                    'state_name': self.state_name,
                    'collection_id': None,
                    'session_id': self.session_id,
                    'client_time_spent_in_secs': self.client_time_spent_in_secs,
                    'params': self.params
                },
                csrf_token
            )
            mock_mark_collection.assert_not_called()

    def test_user_id_invalid_for_collection(self):
        """CT3: user_id is invalid for collection."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch.object(
            learner_progress_services,
            'mark_collection_as_incomplete',
            autospec=True
        ) as mock_mark_collection:
            with self.swap(self, 'user_id', None):
                self.post_json(
                    '/explorehandler/maybe_leave/%s' % self.exploration_id,
                    {
                        'version': self.version,
                        'state_name': self.state_name,
                        'collection_id': self.collection_id,
                        'session_id': self.session_id,
                        'client_time_spent_in_secs': self.client_time_spent_in_secs,
                        'params': self.params
                    },
                    csrf_token
                )
                mock_mark_collection.assert_not_called()

    def test_user_id_and_story_id_valid(self):
        """CT4: user_id and story_id are valid."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch.object(
            story_fetchers,
            'get_story_by_id',
            return_value=mock.Mock(id=self.story_id),
            autospec=True
        ) as mock_get_story:
            self.post_json(
                '/explorehandler/maybe_leave/%s' % self.exploration_id,
                {
                    'version': self.version,
                    'state_name': self.state_name,
                    'collection_id': None,
                    'session_id': self.session_id,
                    'client_time_spent_in_secs': self.client_time_spent_in_secs,
                    'params': self.params
                },
                csrf_token
            )
            mock_get_story.assert_called_once_with(self.story_id)

    def test_story_id_invalid(self):
        """CT5: story_id is invalid."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch.object(
            story_fetchers,
            'get_story_by_id',
            return_value=None,
            autospec=True
        ) as mock_get_story:
            with mock.patch('logging.error') as mock_logging_error:
                self.post_json(
                    '/explorehandler/maybe_leave/%s' % self.exploration_id,
                    {
                        'version': self.version,
                        'state_name': self.state_name,
                        'collection_id': None,
                        'session_id': self.session_id,
                        'client_time_spent_in_secs': self.client_time_spent_in_secs,
                        'params': self.params
                    },
                    csrf_token
                )
                mock_get_story.assert_called_once_with(self.story_id)
                self.assertFalse (mock_logging_error.assert_called_once_with(
                    'Could not find a story corresponding to %s id.' % self.story_id
                ))

    def test_user_id_invalid_for_story(self):
        """CT6: user_id is invalid for story."""
        csrf_token = self.get_new_csrf_token()
        with mock.patch('logging.error') as mock_logging_error:
            with self.swap(self, 'user_id', None):
                self.post_json(
                    '/explorehandler/maybe_leave/%s' % self.exploration_id,
                    {
                        'version': self.version,
                        'state_name': self.state_name,
                        'collection_id': None,
                        'session_id': self.session_id,
                        'client_time_spent_in_secs': self.client_time_spent_in_secs,
                        'params': self.params
                    },
                    csrf_token
                )
                self.assertFalse (mock_logging_error.assert_called_once_with(
                    'Could not find a story corresponding to %s id.' % self.story_id
                ))
