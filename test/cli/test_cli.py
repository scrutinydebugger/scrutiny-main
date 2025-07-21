#    test_cli.py
#        Test the Command Line Interface
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import os
import unittest
import tempfile
import json
import platform
import scrutiny
import datetime
import shutil
from io import StringIO
import sys
from scrutiny.core.basic_types import WatchableType
from scrutiny.core.varmap import VarMap
from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.datalogging import *
from scrutiny.server.sfd_storage import SFDStorage
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from test.artifacts import get_artifact
from test import SkipOnException
from scrutiny.cli import CLI
from scrutiny.exceptions import EnvionmentNotSetUpException
from test import ScrutinyUnitTest
import random
import re


class RedirectStdout:
    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = self.mystdout = StringIO()
        return self

    def __exit__(self, *args):
        sys.stdout = self.old_stdout

    def read(self):
        return self.mystdout.getvalue()


class TestCLI(ScrutinyUnitTest):

    # Generate some metadata file from command line in temp folder and make sure its content is good
    def test_make_metadata(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            filename = os.path.join(tempdirname, 'testfile.json')
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname',
                    '--author', 'unittest', '--output', filename], except_failed=True)
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project_name'], 'testname')

        self.assertEqual(metadata['generation_info']['scrutiny_version'], scrutiny.__version__)
        self.assertEqual(metadata['generation_info']['system_type'], platform.system())
        self.assertEqual(metadata['generation_info']['python_version'], platform.python_version())
        self.assertGreater(metadata['generation_info']['time'], datetime.datetime.now().timestamp() - 5)
        self.assertLess(metadata['generation_info']['time'], datetime.datetime.now().timestamp() + 5)

        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI(tempdirname)
            filename = os.path.join(tempdirname, 'metadata.json')   # default name
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest'], except_failed=True)
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project_name'], 'testname')

    # Extract firmware id from demo binary file and validate the behaviour of the CLI
    def test_get_firmware_id(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            demo_bin = get_artifact('demobin.elf')
            with open(get_artifact('demobin_firmwareid')) as f:
                demobin_firmware_id = f.read()
            temp_bin = os.path.join(tempdirname, 'demobin.elf')
            shutil.copyfile(demo_bin, temp_bin)

            # Write firmware id to stdout and compare with reference
            with RedirectStdout() as stdout:
                cli.run(['get-firmware-id', temp_bin], except_failed=True)
                firmwareid = stdout.read()
            self.assertEqual(firmwareid, demobin_firmware_id)

            # Write firmware id to file and compare with reference
            output_file = os.path.join(tempdirname, 'temp_firmwareid')
            cli.run(['get-firmware-id', temp_bin, '--output', output_file], except_failed=True)  # Write firmware id to file
            with open(output_file) as f:
                outputted_firmwareid = f.read()
            self.assertEqual(outputted_firmwareid, demobin_firmware_id)

    def test_tag_firmware_id(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            demo_bin = get_artifact('demobin.elf')
            temp_bin = os.path.join(tempdirname, 'demobin.elf')
            temp_bin_tagged = os.path.join(tempdirname, 'demobin_tagged.elf')
            temp_bin2 = os.path.join(tempdirname, 'demobin2.elf')
            shutil.copyfile(demo_bin, temp_bin)
            shutil.copyfile(demo_bin, temp_bin2)    # Will be tagged inplace

            with self.assertRaises(Exception):
                cli.run(['tag-firmware-id', temp_bin], except_failed=True)

            with self.assertRaises(Exception):
                cli.run(['tag-firmware-id', temp_bin, 'somefile', '--inplace'], except_failed=True)

            cli.run(['tag-firmware-id', temp_bin, temp_bin_tagged], except_failed=True)
            cli.run(['tag-firmware-id', temp_bin2, '--inplace'], except_failed=True)

            # Write the firmware id to the demobin and catch its from stdout. Make sure file has changed
            with open(temp_bin, 'rb') as f:
                tempbin_content = f.read()

            with open(temp_bin2, 'rb') as f:
                tempbin2_content = f.read()

            with open(temp_bin_tagged, 'rb') as f:
                tempbin_tagged_content = f.read()

            self.assertFalse(tempbin_content == tempbin_tagged_content)
            self.assertTrue(tempbin2_content == tempbin2_content)

    # Read a demo firmware binary and make varmap file. We don't check the content, just that it is valid varmap.
    @SkipOnException(EnvionmentNotSetUpException)
    def test_elf2varmap(self):
        cli = CLI()
        demobin_path = get_artifact('demobin.elf')

        with RedirectStdout() as stdout:
            cli.run(['elf2varmap', demobin_path], except_failed=True)
            VarMap(stdout.read())  # make sure the output is loadable. Don't check content, there's another test suite for that

        with tempfile.TemporaryDirectory() as tempdirname:
            outputfile = os.path.join(tempdirname, 'varmap.json')
            cli.run(['elf2varmap', demobin_path, '--output', outputfile], except_failed=True)
            VarMap(outputfile)  # make sure the output is loadable. Don't check content, there's another test suite for that

    # Test all commands related to manipulating Scrutiny Firmware Description
    @SkipOnException(EnvionmentNotSetUpException)
    def test_make_sfd_and_install(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            with SFDStorage.use_temp_folder():
                cli = CLI()
                demo_bin = get_artifact('demobin.elf')
                temp_bin = os.path.join(tempdirname, 'demobin.elf')
                sfd_name = os.path.join(tempdirname, 'myfile.sfd')
                alias_file_1 = get_artifact(os.path.join('sfd_material', 'demobin_aliases.json'))
                shutil.copyfile(demo_bin, temp_bin)

                with open(get_artifact('demobin_firmwareid')) as f:
                    demobin_firmware_id = f.read()

                cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname',
                        '--author', 'unittest', '--output', tempdirname], except_failed=True)
                cli.run(['get-firmware-id', temp_bin, '--output', tempdirname], except_failed=True)
                cli.run(['tag-firmware-id', temp_bin, '--inplace'], except_failed=True)
                cli.run(['elf2varmap', temp_bin, '--output', tempdirname], except_failed=True)
                cli.run(['add-alias', tempdirname, '--file', alias_file_1], except_failed=True)
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)
                self.assertFalse(SFDStorage.is_installed(demobin_firmware_id))

                cli.run(['make-sfd', tempdirname, sfd_name, '--install'], except_failed=True)     # install while making
                self.assertTrue(SFDStorage.is_installed(demobin_firmware_id))
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)    # uninstall
                self.assertFalse(SFDStorage.is_installed(demobin_firmware_id))
                cli.run(['install-sfd', sfd_name], except_failed=True)                            # install with dedicated command
                self.assertTrue(SFDStorage.is_installed(demobin_firmware_id))
                sfd = SFDStorage.get(demobin_firmware_id)
                self.assertEqual(sfd.get_firmware_id_ascii(), demobin_firmware_id)  # Load and check id.
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)    # cleanup

    def test_list_sfd(self):
        cli = CLI()
        sfd1_filename = get_artifact('test_sfd_1.sfd')
        sfd2_filename = get_artifact('test_sfd_2.sfd')

        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(sfd1_filename, ignore_exist=True)
            sfd2 = SFDStorage.install(sfd2_filename, ignore_exist=True)

            with RedirectStdout() as stdout:
                cli.run(['list-sfd'])  # Make sure no exception is raised
                nbline = stdout.read().count('\n')
                self.assertGreaterEqual(nbline, 3)  # 2 SFD + total number

            SFDStorage.uninstall(sfd1.get_firmware_id_ascii())
            SFDStorage.uninstall(sfd2.get_firmware_id_ascii())

    def test_append_alias_to_sfd_folder(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            varmap_file = get_artifact(os.path.join('sfd_material', 'varmap.json'))
            alias_file_1 = get_artifact(os.path.join('sfd_material', 'alias1.json'))
            alias_file_2 = get_artifact(os.path.join('sfd_material', 'alias2.json'))
            shutil.copyfile(varmap_file, os.path.join(tempdirname, 'varmap.json'))
            cli = CLI()

            cli.run(['add-alias', tempdirname, '--file', alias_file_1], except_failed=True)
            cli.run(['add-alias', tempdirname, '--file', alias_file_2], except_failed=True)

            cli.run(['add-alias', tempdirname,
                     '--fullpath', '/alias/command_line_added',
                     '--target', '/path1/path2/some_int32',
                     '--gain', '5.2',
                     '--offset', '2.5',
                     '--min', '0',
                     '--max', '100'
                     ], except_failed=True)

            with open(os.path.join(tempdirname, 'alias.json')) as f:
                alias_dict = json.load(f)

            with open(alias_file_1) as f:
                alias1_dict = json.load(f)

            with open(alias_file_2) as f:
                alias2_dict = json.load(f)

            for k in alias1_dict:
                self.assertIn(k, alias_dict)
                for k2 in alias1_dict[k]:
                    self.assertIn(k2, alias_dict[k])
                    self.assertEqual(alias_dict[k][k2], alias1_dict[k][k2])

            for k in alias2_dict:
                self.assertIn(k, alias_dict)
                for k2 in alias2_dict[k]:
                    self.assertIn(k2, alias_dict[k])
                    self.assertEqual(alias_dict[k][k2], alias2_dict[k][k2])

            self.assertIn('/alias/command_line_added', alias_dict)
            entry = alias_dict['/alias/command_line_added']
            self.assertEqual(entry['target'], "/path1/path2/some_int32")
            self.assertEqual(entry['gain'], 5.2)
            self.assertEqual(entry['offset'], 2.5)
            self.assertEqual(entry['min'], 0)
            self.assertEqual(entry['max'], 100)

    def test_append_alias_to_sfd_file(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            sfd_filename = get_artifact('test_sfd_1.sfd')
            target_filename = os.path.join(tempdirname, 'test_sfd_1.sfd')
            shutil.copy(sfd_filename, target_filename)

            sfd = FirmwareDescription(target_filename)
            aliases = sfd.get_aliases()
            self.assertNotIn('/alias/command_line_added', aliases)

            cli = CLI()
            cli.run(['add-alias', target_filename,
                     '--fullpath', '/alias/command_line_added',
                     '--target', '/path1/path2/some_int32',
                     '--gain', '5.2',
                     '--offset', '2.5',
                     '--min', '0',
                     '--max', '100'
                     ])

            sfd = FirmwareDescription(target_filename)
            aliases = sfd.get_aliases()

            self.assertIn('/alias/command_line_added', aliases)
            alias = aliases['/alias/command_line_added']
            self.assertEqual(alias.get_fullpath(), '/alias/command_line_added')
            self.assertEqual(alias.get_target(), '/path1/path2/some_int32')
            self.assertEqual(alias.get_target_type(), WatchableType.Variable)
            self.assertEqual(alias.get_gain(), 5.2)
            self.assertEqual(alias.get_offset(), 2.5)
            self.assertEqual(alias.get_min(), 0.0)
            self.assertEqual(alias.get_max(), 100.0)

    def test_append_alias_to_install_sfd_by_id(self):
        with SFDStorage.use_temp_folder():
            sfd = SFDStorage.install(get_artifact('test_sfd_1.sfd'))
            firmwareid = sfd.get_firmware_id_ascii()
            del sfd

            cli = CLI()
            cli.run(['add-alias', firmwareid,
                     '--fullpath', '/alias/command_line_added',
                     '--target', '/rpv/x123',
                     '--gain', '5.2',
                     '--offset', '2.5',
                     '--min', '0',
                     '--max', '100'
                     ])

            sfd = SFDStorage.get(firmwareid)
            aliases = sfd.get_aliases()
            self.assertIn('/alias/command_line_added', aliases)
            alias = aliases['/alias/command_line_added']
            self.assertEqual(alias.get_fullpath(), '/alias/command_line_added')
            self.assertEqual(alias.get_target(), '/rpv/x123')
            self.assertEqual(alias.get_target_type(), WatchableType.RuntimePublishedValue)
            self.assertEqual(alias.get_gain(), 5.2)
            self.assertEqual(alias.get_offset(), 2.5)
            self.assertEqual(alias.get_min(), 0.0)
            self.assertEqual(alias.get_max(), 100.0)

    def test_datalog_info(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1", acq_time=datetime.datetime.now())
            axis1 = AxisDefinition("Axis-1", 111)
            acq1.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq1.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)
            acq2 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #2",
                                          acq_time=datetime.datetime.now() - datetime.timedelta(seconds=30))
            acq2.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq2.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)

            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)

            cli = CLI()
            with RedirectStdout() as stdout:
                cli.run(['datalog-info'])  # Make sure no exception is raised
                output = stdout.read()

            self.assertIsNotNone(re.search(r'Acquisitions count:\s+2', output), output)
            self.assertIsNotNone(re.search(r'Storage structure hash:\s+%s' % DataloggingStorage.get_db_hash(), output), output)
            m = re.search(r'Oldest acquisition:\s+([^\n]+)', output)
            self.assertIsNotNone(m)
            oldest = m.groups(1)[0]

            m = re.search(r'Newest acquisition:\s+([^\n]+)', output)
            self.assertIsNotNone(m)
            newest = m.groups(1)[0]

            oldest = datetime.datetime.fromisoformat(oldest)
            newest = datetime.datetime.fromisoformat(newest)
            self.assertEqual(newest - oldest, datetime.timedelta(seconds=30))

            m = re.search(r'Storage location:\s+([^\n]+)', output)
            self.assertIsNotNone(m)
            storage_file = m.groups(1)[0]
            self.assertTrue(os.path.isfile(storage_file))

    def test_list_datalog(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1", acq_time=datetime.datetime.now(), firmware_name="foo.bar")
            axis1 = AxisDefinition("Axis-1", 111)
            acq1.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq1.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)
            acq2 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #2",
                                          acq_time=datetime.datetime.now() - datetime.timedelta(seconds=30))
            acq2.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq2.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)

            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)

            cli = CLI()
            with RedirectStdout() as stdout:
                cli.run(['list-datalog'])  # Make sure no exception is raised
                output = stdout.read()

            output = output.strip()
            self.assertEqual(output.count('\n'), 3 - 1)  # Header + 2 acquisition -1
            self.assertIn(acq1.reference_id, output)
            self.assertIn(acq1.name, output)
            self.assertNotIn(acq1.firmware_id, output)
            self.assertIn(acq2.reference_id, output)
            self.assertIn(acq2.name, output)

            with RedirectStdout() as stdout:
                cli.run(['list-datalog', '--firmware'])  # Make sure no exception is raised
                output = stdout.read()

            output = output.strip()
            self.assertEqual(output.count('\n'), 3 - 1)  # Header + 2 acquisition -1
            self.assertIn(acq1.reference_id, output)
            self.assertIn(acq1.name, output)
            self.assertIn(acq1.firmware_id, output)
            self.assertIn(acq2.reference_id, output)
            self.assertIn(acq2.name, output)

            DataloggingStorage.clear_all()

            with RedirectStdout() as stdout:
                cli.run(['list-datalog'])  # Make sure no exception is raised
                output = stdout.read()

            self.assertEqual('No acquisitions', output.strip())

    def test_delete_datalog(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1", acq_time=datetime.datetime.now())
            axis1 = AxisDefinition("Axis-1", 111)
            acq1.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq1.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)
            acq2 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #2",
                                          acq_time=datetime.datetime.now() - datetime.timedelta(seconds=30))
            acq2.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq2.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)

            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)

            self.assertEqual(DataloggingStorage.count(), 2)
            cli = CLI()
            with RedirectStdout() as stdout:
                cli.run(['delete-datalog', '--id', acq2.reference_id])  # Make sure no exception is raised

            self.assertEqual(DataloggingStorage.count(), 1)
            DataloggingStorage.save(acq2)
            self.assertEqual(DataloggingStorage.count(), 2)

            with RedirectStdout() as stdout:
                cli.run(['delete-datalog', '--all'])  # Make sure no exception is raised

            self.assertEqual(DataloggingStorage.count(), 0)

    def test_export_datalog_csv(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1", acq_time=datetime.datetime.now())
            axis1 = AxisDefinition("Axis-1", 111)
            acq1.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq1.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)
            acq2 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #2",
                                          acq_time=datetime.datetime.now() - datetime.timedelta(seconds=30))
            acq2.set_xdata(DataSeries([random.random() for x in range(10)]))
            acq2.add_data(DataSeries([random.random() for x in range(10)], logged_watchable=LoggedWatchable("/a/b", WatchableType.Variable)), axis1)

            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)

            with tempfile.TemporaryDirectory() as tempdirname:
                file1 = os.path.join(tempdirname, 'file1.csv')
                file2 = os.path.join(tempdirname, 'file2.csv')
                cli = CLI()
                with RedirectStdout() as stdout:
                    cli.run(['export-datalog', acq2.reference_id, '--csv', file1])  # Make sure no exception is raised

                acq2.to_csv(file2)

                self.assertTrue(os.path.isfile(file1))
                self.assertTrue(os.path.isfile(file2))

                with open(file1) as f1:
                    with open(file2) as f2:
                        self.assertEqual(f1.read(), f2.read())


if __name__ == '__main__':
    import unittest
    unittest.main()
