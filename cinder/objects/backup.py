#    Copyright 2015 Intel Corporation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import base64
import binascii

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_versionedobjects import fields
import six

from cinder import db
from cinder import exception
from cinder.i18n import _
from cinder import objects
from cinder.objects import base
from cinder import utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


@base.CinderObjectRegistry.register
class Backup(base.CinderPersistentObject, base.CinderObject,
             base.CinderObjectDictCompat):
    # Version 1.0: Initial version
    # Version 1.1: Add new field num_dependent_backups and extra fields
    #              is_incremental and has_dependent_backups.
    VERSION = '1.1'

    fields = {
        'id': fields.UUIDField(),

        'user_id': fields.UUIDField(),
        'project_id': fields.UUIDField(),

        'volume_id': fields.UUIDField(),
        'host': fields.StringField(nullable=True),
        'availability_zone': fields.StringField(nullable=True),
        'container': fields.StringField(nullable=True),
        'parent_id': fields.StringField(nullable=True),
        'status': fields.StringField(nullable=True),
        'fail_reason': fields.StringField(nullable=True),
        'size': fields.IntegerField(),

        'display_name': fields.StringField(nullable=True),
        'display_description': fields.StringField(nullable=True),

        # NOTE(dulek): Metadata field is used to store any strings by backup
        # drivers, that's why it can't be DictOfStringsField.
        'service_metadata': fields.StringField(nullable=True),
        'service': fields.StringField(nullable=True),

        'object_count': fields.IntegerField(),

        'temp_volume_id': fields.StringField(nullable=True),
        'temp_snapshot_id': fields.StringField(nullable=True),
        'num_dependent_backups': fields.IntegerField(),
    }

    obj_extra_fields = ['name', 'is_incremental', 'has_dependent_backups']

    @property
    def name(self):
        return CONF.backup_name_template % self.id

    @property
    def is_incremental(self):
        return bool(self.parent_id)

    @property
    def has_dependent_backups(self):
        return bool(self.num_dependent_backups)

    def obj_make_compatible(self, primitive, target_version):
        """Make an object representation compatible with a target version."""
        super(Backup, self).obj_make_compatible(primitive, target_version)
        target_version = utils.convert_version_to_tuple(target_version)

    @staticmethod
    def _from_db_object(context, backup, db_backup):
        for name, field in backup.fields.items():
            value = db_backup.get(name)
            if isinstance(field, fields.IntegerField):
                value = value if value is not None else 0
            backup[name] = value

        backup._context = context
        backup.obj_reset_changes()
        return backup

    @base.remotable_classmethod
    def get_by_id(cls, context, id):
        db_backup = db.backup_get(context, id)
        return cls._from_db_object(context, cls(context), db_backup)

    @base.remotable
    def create(self):
        if self.obj_attr_is_set('id'):
            raise exception.ObjectActionError(action='create',
                                              reason='already created')
        updates = self.cinder_obj_get_changes()

        db_backup = db.backup_create(self._context, updates)
        self._from_db_object(self._context, self, db_backup)

    @base.remotable
    def save(self):
        updates = self.cinder_obj_get_changes()
        if updates:
            db.backup_update(self._context, self.id, updates)

        self.obj_reset_changes()

    @base.remotable
    def destroy(self):
        with self.obj_as_admin():
            db.backup_destroy(self._context, self.id)

    @staticmethod
    def decode_record(backup_url):
        """Deserialize backup metadata from string into a dictionary.

        :raises: InvalidInput
        """
        try:
            return jsonutils.loads(base64.decodestring(backup_url))
        except binascii.Error:
            msg = _("Can't decode backup record.")
        except ValueError:
            msg = _("Can't parse backup record.")
        raise exception.InvalidInput(reason=msg)

    @base.remotable
    def encode_record(self, **kwargs):
        """Serialize backup object, with optional extra info, into a string."""
        kwargs.update(self)
        retval = jsonutils.dumps(kwargs)
        if six.PY3:
            retval = retval.encode('utf-8')
        return base64.encodestring(retval)


@base.CinderObjectRegistry.register
class BackupList(base.ObjectListBase, base.CinderObject):
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('Backup'),
    }
    child_versions = {
        '1.0': '1.0'
    }

    @base.remotable_classmethod
    def get_all(cls, context, filters=None):
        backups = db.backup_get_all(context, filters)
        return base.obj_make_list(context, cls(context), objects.Backup,
                                  backups)

    @base.remotable_classmethod
    def get_all_by_host(cls, context, host):
        backups = db.backup_get_all_by_host(context, host)
        return base.obj_make_list(context, cls(context), objects.Backup,
                                  backups)

    @base.remotable_classmethod
    def get_all_by_project(cls, context, project_id, filters=None):
        backups = db.backup_get_all_by_project(context, project_id, filters)
        return base.obj_make_list(context, cls(context), objects.Backup,
                                  backups)

    @base.remotable_classmethod
    def get_all_by_volume(cls, context, volume_id, filters=None):
        backups = db.backup_get_all_by_volume(context, volume_id, filters)
        return base.obj_make_list(context, cls(context), objects.Backup,
                                  backups)
