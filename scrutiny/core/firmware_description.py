#    firmware_description.py
#        Contains the class that represent a Scrutiny Firmware Description file.
#        A .sfd is a file that holds all the data related to a firmware and is identified
#        by a unique ID.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['SFDGenerationInfo', 'SFDMetadata', 'FirmwareDescription', 'GenerationInfoTypedDict', 'MetadataTypedDict']

import zipfile
import os
import json
import logging
import platform
from datetime import datetime
from dataclasses import dataclass

import scrutiny
import scrutiny.core.firmware_id as firmware_id
from scrutiny.core.varmap import VarMap
from scrutiny.core.variable import Variable
from scrutiny.core.variable_factory import VariableFactory
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.core.basic_types import WatchableType
from scrutiny.core.alias import Alias
from scrutiny.core.basic_types import *

from scrutiny.tools.typing import *
from scrutiny.tools import validation


class GenerationInfoTypedDict(TypedDict, total=False):
    """
    Metadata about the environment of the file creator
    """
    time: Optional[int]
    python_version: Optional[str]
    scrutiny_version: Optional[str]
    system_type: Optional[str]


class MetadataTypedDict(TypedDict, total=False):
    """
    Firmware Description metadata. Used for display in the UI (Communicated through API)
    """
    project_name: Optional[str]
    author: Optional[str]
    version: Optional[str]
    generation_info: Optional[GenerationInfoTypedDict]


@dataclass(frozen=True, slots=True)
class SFDGenerationInfo:
    """(Immutable struct) Metadata relative to the generation of the SFD"""

    timestamp: Optional[datetime]
    """Date/time at which the SFD has been created. ``None`` if not available"""
    python_version: Optional[str]
    """Python version with which the SFD has been created. ``None`` if not available"""
    scrutiny_version: Optional[str]
    """Scrutiny version with which the SFD has been created. ``None`` if not available"""
    system_type: Optional[str]
    """Type of system on which the SFD has been created. Value given by Python `platform.system()`. ``None`` if not available"""

    @classmethod
    def make(cls) -> "SFDGenerationInfo":
        return SFDGenerationInfo(
            timestamp=datetime.now(),
            python_version=platform.python_version(),
            scrutiny_version=scrutiny.__version__,
            system_type=platform.system()
        )

    def __post_init__(self) -> None:
        validation.assert_type_or_none(self.timestamp, 'timestamp', datetime)
        validation.assert_type_or_none(self.python_version, 'python_version', str)
        validation.assert_type_or_none(self.scrutiny_version, 'scrutiny_version', str)
        validation.assert_type_or_none(self.system_type, 'system_type', str)

    def to_dict(self) -> GenerationInfoTypedDict:
        timestamp = None
        if self.timestamp is not None:
            timestamp = int(round(self.timestamp.timestamp()))
        return {
            'python_version': self.python_version,
            'scrutiny_version': self.scrutiny_version,
            'system_type': self.system_type,
            'time': timestamp
        }


@dataclass(frozen=True, slots=True)
class SFDMetadata:
    """(Immutable struct) All the metadata associated with a Scrutiny Firmware Description"""

    project_name: Optional[str]
    """Name of the project. ``None`` if not available"""
    author: Optional[str]
    """The author of this firmware. ``None`` if not available"""
    version: Optional[str]
    """The version string of this firmware. ``None`` if not available"""
    generation_info: SFDGenerationInfo
    """Metadata regarding the creation environment of the SFD file."""

    def __post_init__(self) -> None:
        validation.assert_type_or_none(self.project_name, 'project_name', str)
        validation.assert_type_or_none(self.author, 'author', str)
        validation.assert_type_or_none(self.version, 'version', str)
        validation.assert_type(self.generation_info, 'generation_info', SFDGenerationInfo)

    def to_dict(self) -> MetadataTypedDict:
        return {
            'project_name': self.project_name,
            'author': self.author,
            'version': self.version,
            'generation_info': self.generation_info.to_dict()
        }


class FirmwareDescription:
    """
    Scrutiny Firmware Description (SFD) is an object that contains all the relevant data about a firmware.
    It mainly knows its firmware ID and the list of variables with their location.
    Upon connection with a device, the correct SFD must be loaded, found with the firmware ID
    """
    COMPRESSION_TYPE = zipfile.ZIP_DEFLATED

    VARMAP_FILENAME: str = 'varmap.json'
    METADATA_FILENAME: str = 'metadata.json'
    FIRMWAREID_FILENAME: str = 'firmwareid'
    ALIAS_FILE: str = 'alias.json'

    REQUIRED_FILES: List[str] = [
        FIRMWAREID_FILENAME,
        METADATA_FILENAME,
        VARMAP_FILENAME
    ]

    varmap: VarMap
    metadata: SFDMetadata
    firmwareid: bytes
    aliases: Dict[str, Alias]
    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, firmwareid: bytes, varmap: VarMap, metadata: SFDMetadata):
        self.firmwareid = firmwareid
        self.varmap = varmap
        self.metadata = metadata
        self.aliases = {}

    @classmethod
    def load_from_filesystem(cls, file_folder: str) -> "FirmwareDescription":
        if os.path.isdir(file_folder):
            return cls.load_from_folder(file_folder)
        elif os.path.isfile(file_folder):
            return cls.load_from_file(file_folder)

        raise FileNotFoundError(f"Cannot find {file_folder}")

    @classmethod
    def load_from_folder(cls, folder: str) -> "FirmwareDescription":
        """
        Reads a folder just like if it was an unzipped Scrutiny Firmware Description (SFD) file.
        Used to build the SFD
        """
        if not os.path.isdir(folder):
            raise FileNotFoundError("Folder %s does not exist" % folder)

        for file in cls.REQUIRED_FILES:
            if not os.path.isfile(os.path.join(folder, file)):
                raise FileNotFoundError('Missing %s' % file)

        metadata_file = os.path.join(folder, cls.METADATA_FILENAME)
        with open(metadata_file, 'rb') as f:
            metadata = cls.read_metadata(f)

        with open(os.path.join(folder, cls.FIRMWAREID_FILENAME), 'rb') as f:
            firmwareid = cls.read_firmware_id(f)

        varmap = cls.read_varmap_from_filesystem(folder)

        sfd = FirmwareDescription(firmwareid, varmap, metadata)

        if os.path.isfile(os.path.join(folder, cls.ALIAS_FILE)):
            with open(os.path.join(folder, cls.ALIAS_FILE), 'rb') as f:
                aliases = cls.read_aliases(f, sfd.varmap, suppress_errors=True)
                sfd.append_aliases(aliases)

        return sfd

    @classmethod
    def read_metadata_from_sfd_file(cls, filename: str) -> SFDMetadata:
        with zipfile.ZipFile(filename, mode='r', compression=cls.COMPRESSION_TYPE) as sfd:
            with sfd.open(cls.METADATA_FILENAME) as f:
                metadata = cls.read_metadata(f)

        return metadata

    @classmethod
    def load_from_file(cls, filename: str) -> "FirmwareDescription":
        """Reads a Scrutiny Firmware Description file (.sfd) which is just a .zip containing bunch of json files """
        with zipfile.ZipFile(filename, mode='r', compression=cls.COMPRESSION_TYPE) as zipsfd:
            with zipsfd.open(cls.FIRMWAREID_FILENAME) as f:
                firmwareid = cls.read_firmware_id(f)  # This is not a Json file. Content is raw.

            with zipsfd.open(cls.METADATA_FILENAME, 'r') as f:
                metadata = cls.read_metadata(f)   # This is a json file

            with zipsfd.open(cls.VARMAP_FILENAME, 'r') as f:
                varmap = VarMap.from_file_content(f.read())  # Json file

            sfd = FirmwareDescription(firmwareid, varmap, metadata)
            if cls.ALIAS_FILE in zipsfd.namelist():
                with zipsfd.open(cls.ALIAS_FILE, 'r') as f:
                    sfd.append_aliases(cls.read_aliases(f, varmap, suppress_errors=True))

            return sfd

    @classmethod
    def read_firmware_id_from_sfd_file(cls, filename: str) -> bytes:
        with zipfile.ZipFile(filename, mode='r', compression=cls.COMPRESSION_TYPE) as sfd:
            with sfd.open(cls.FIRMWAREID_FILENAME) as f:
                return cls.read_firmware_id(f)

    @classmethod
    def read_firmware_id(cls, f: IO[bytes]) -> bytes:
        return bytes.fromhex(f.read().decode('ascii'))

    @classmethod
    def read_metadata(cls, f: IO[bytes]) -> SFDMetadata:
        FIELDS_TYPE: TypeAlias = List[Tuple[str, Type[Any]]]

        metadata_dict = cast(MetadataTypedDict, json.loads(f.read().decode('utf8')))
        if not isinstance(metadata_dict, dict):
            metadata_dict = {}

        def remove_bad_fields(obj: Any, fields: FIELDS_TYPE) -> None:
            obj2 = cast(Dict[str, Any], obj)
            for field in fields:
                if field[0] in obj2 and not isinstance(obj2[field[0]], field[1]):
                    del obj2[field[0]]

        fields1: FIELDS_TYPE = [
            ('project_name', str),
            ('author', str),
            ('version', str),
            ('generation_info', dict)
        ]

        remove_bad_fields(metadata_dict, fields1)

        if 'generation_info' in metadata_dict:
            fields2: FIELDS_TYPE = [
                ('python_version', str),
                ('scrutiny_version', str),
                ('system_type', str),
                ('time', int)
            ]
            remove_bad_fields(metadata_dict['generation_info'], fields2)

        generation_timestamp = None
        generation_info = cast(Optional[GenerationInfoTypedDict], metadata_dict.get('generation_info', {}))
        if generation_info is None:
            generation_info = cast(GenerationInfoTypedDict, {})

        generation_timestamp = generation_info.get('time', None)

        return SFDMetadata(
            author=metadata_dict.get('author', None),
            project_name=metadata_dict.get('project_name', None),
            version=metadata_dict.get('version', None),
            generation_info=SFDGenerationInfo(
                python_version=generation_info.get('python_version', None),
                scrutiny_version=generation_info.get('scrutiny_version', None),
                system_type=generation_info.get('system_type', None),
                timestamp=None if generation_timestamp is None else datetime.fromtimestamp(generation_timestamp),
            )
        )

    @classmethod
    def read_aliases(cls, f: IO[bytes], varmap: VarMap, suppress_errors: bool = True) -> Dict[str, Alias]:
        aliases_raw: Dict[str, Any] = json.loads(f.read().decode('utf8'))
        aliases: Dict[str, Alias] = {}
        for k in aliases_raw:
            alias = Alias.from_dict(k, aliases_raw[k])
            try:
                alias.set_target_type(cls.get_alias_target_type(alias, varmap))
            except Exception as e:
                if suppress_errors:
                    cls.logger.error("Cannot read alias. %s" % str(e))
                else:
                    raise e

            aliases[k] = alias

        return aliases

    @classmethod
    def get_alias_target_type(cls, alias: Alias, varmap: VarMap) -> WatchableType:
        """ Finds the referred entry and gives this datatype. Alias do not have a datatype by themselves """
        if varmap.has_var(alias.get_target()):
            return WatchableType.Variable
        elif Datastore.is_rpv_path(alias.get_target()):
            return WatchableType.RuntimePublishedValue
        else:
            raise Exception('Alias %s is referencing %s which is not a valid Variable or Runtime Published Value' %
                            (alias.get_fullpath(), alias.get_target()))

    @classmethod
    def read_varmap_from_filesystem(cls, path: str) -> VarMap:
        if os.path.isfile(path):
            fullpath = path
        elif os.path.isdir(path):
            fullpath = os.path.join(path, cls.VARMAP_FILENAME)
        else:
            raise Exception('Cannot find varmap file at %s' % path)

        return VarMap.from_file(fullpath)

    def append_aliases(self, aliases: Union[List[Alias], Dict[str, Alias]]) -> None:
        """Add some aliases to the actual SFD"""
        if isinstance(aliases, list):
            for alias in aliases:
                if alias.fullpath not in self.aliases:
                    self.aliases[alias.fullpath] = alias
                else:
                    self.logger.warning(f'Duplicate alias {alias.fullpath}. Dropping')
        elif isinstance(aliases, dict):
            for unique_path in aliases:
                if unique_path not in self.aliases:
                    self.aliases[unique_path] = aliases[unique_path]
                else:
                    self.logger.warning(f'Duplicate alias {unique_path}. Dropping')
        else:
            raise ValueError("Aliases must be passed as a list or a dict.")

    def write(self, filename: str) -> None:
        """SFD file format is just a .zip with a bunch of JSON (and a firmwareid file)"""
        with zipfile.ZipFile(filename, mode='w', compression=self.COMPRESSION_TYPE) as outzip:
            outzip.writestr(self.FIRMWAREID_FILENAME, self.firmwareid.hex())
            outzip.writestr(self.METADATA_FILENAME, json.dumps(self.metadata.to_dict(), indent=4))
            outzip.writestr(self.VARMAP_FILENAME, self.varmap.get_json())
            outzip.writestr(self.ALIAS_FILE, self.serialize_aliases(list(self.aliases.values())))

    @classmethod
    def serialize_aliases(cls, aliases: Union[Dict[str, Alias], List[Alias]]) -> bytes:
        """ 
        Takes bunch of alias and return a JSON containing a dict structure like this
        [alias1.fullpath] => alias1,  [alias2.fullpath] => alias2 
        """
        if isinstance(aliases, list):
            zipped = zip(
                [alias.get_fullpath() for alias in aliases],
                [alias.to_dict() for alias in aliases]
            )
        elif isinstance(aliases, dict):
            zipped = zip(
                [aliases[k].get_fullpath() for k in aliases],
                [aliases[k].to_dict() for k in aliases]
            )
        else:
            ValueError('Require a list or a dict of aliases')
        return json.dumps(dict(zipped), indent=4).encode('utf8')

    def get_firmware_id(self) -> bytes:
        return self.firmwareid

    def get_firmware_id_ascii(self) -> str:
        return self.firmwareid.hex().lower()

    def get_endianness(self) -> Endianness:
        return self.varmap.get_endianness()

    def validate(self) -> None:
        if not hasattr(self, 'metadata') or not hasattr(self, 'varmap') or not hasattr(self, 'firmwareid'):
            raise Exception('Firmware Description not loaded correctly')

        self.validate_metadata()
        self.validate_firmware_id()
        self.varmap.validate()

    def validate_firmware_id(self) -> None:
        """Expects a Firmware ID to have the same length as the default placeholder"""
        if len(self.firmwareid) != self.firmware_id_length():
            raise Exception('Firmware ID seems to be the wrong length. Found %d bytes, expected %d bytes' %
                            (len(self.firmwareid), len(firmware_id.PLACEHOLDER)))

    def validate_metadata(self) -> None:
        if self.metadata.project_name is None:
            self.logger.warning('No valid project name defined in %s' % self.METADATA_FILENAME)

        if self.metadata.version is None:
            self.logger.warning('No valid version defined in %s' % self.METADATA_FILENAME)

        if self.metadata.author is None:
            self.logger.warning('No valid author defined in %s' % self.METADATA_FILENAME)

    def get_vars_for_datastore(self) -> Generator[Tuple[str, Union[Variable, VariableFactory]], None, None]:
        """Returns all variables in this SFD with a Generator to avoid consuming memory."""
        yield from self.varmap.iterate_vars()

    def get_aliases_for_datastore(self, entry_type: Optional[WatchableType] = None) -> Generator[Tuple[str, Alias], None, None]:
        """Returns all alias in this SFD with a Generator to avoid consuming memory."""
        for k in self.aliases:
            if entry_type is None or self.aliases[k].get_target_type() == entry_type:
                yield (self.aliases[k].get_fullpath(), self.aliases[k])

    def get_aliases(self) -> Dict[str, Alias]:
        return self.aliases

    def get_metadata(self) -> SFDMetadata:
        return self.metadata

    @classmethod
    def firmware_id_length(cls) -> int:
        return len(firmware_id.PLACEHOLDER)
