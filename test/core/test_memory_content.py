#    test_memory_content.py
#        Test the MemoryContent class functionalities. Make sure it correctly writes and read
#        and also agglomerate contiguous clusters
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

from scrutiny.core.memory_content import MemoryContent, Cluster
import tempfile
import os
from test import ScrutinyUnitTest


class TestCluster(ScrutinyUnitTest):
    def test_read_write_with_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=True)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(cluster[10], b'\xFF')
        self.assertEqual(cluster[10:20], b'\xFF' * 10)
        self.assertEqual(cluster[50:], b'\xFF' * 50)

        with self.assertRaises(IndexError):
            cluster[101]

        cluster.write(bytes([1, 2, 3]))
        self.assertEqual(bytes(cluster[0:5]), b'\x01\x02\x03\xFF\xFF')

        cluster.write(bytes([4, 5, 6]), offset=50)
        self.assertEqual(bytes(cluster[49:54]), b'\xFF\x04\x05\x06\xFF')

    def test_read_write_no_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=False)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(cluster[10], b'\x00')
        self.assertEqual(cluster[10:20], b'\x00' * 10)
        self.assertEqual(cluster[50:], b'\x00' * 50)

        with self.assertRaises(IndexError):
            cluster[100]

        cluster.write(bytes([1, 2, 3]))
        self.assertEqual(bytes(cluster[0:5]), b'\x00' * 5)

        cluster.write(bytes([4, 5, 6]), offset=50)
        self.assertEqual(bytes(cluster[49:54]), b'\x00' * 5)

    def test_resize_with_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=True)
        cluster.shrink(50)
        self.assertEqual(len(cluster), 50)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 50)

        cluster.extend(100, b'\xAA' * 50)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 50 + b'\xAA' * 50)

        cluster.extend(200)  # missing data, fill with 0
        self.assertEqual(len(cluster), 200)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 50 + b'\xAA' * 50 + b'\x00' * 100)

        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=True)
        with self.assertRaises(Exception):
            cluster.extend(101, bytes([1, 2]))  # One extra byte

    def test_resize_no_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=False)
        cluster.shrink(50)
        self.assertEqual(len(cluster), 50)
        self.assertEqual(bytes(cluster.data), b'\x00' * 50)

        cluster.extend(100, b'\xAA' * 50)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(bytes(cluster.data), b'\x00' * 50 + b'\x00' * 50)

        cluster.extend(1000)  # data not needed. No exception

        cluster = Cluster(start_addr=0x1000, size=100, data=b'\xFF' * 100, has_data=True)
        with self.assertRaises(Exception):
            cluster.extend(101, bytes([1, 2]))  # One extra byte


class TestClusterCharBit16(ScrutinyUnitTest):
    def test_read_write_with_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=True)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(cluster[10], b'\xFF' * 2)        # 1 device byte = 2 python bytes
        self.assertEqual(cluster[10:20], b'\xFF' * 20)    # 10 device bytes = 20 python bytes
        self.assertEqual(cluster[50:], b'\xFF' * 100)     # 50 device bytes = 100 python bytes

        with self.assertRaises(IndexError):
            cluster[100]

        with self.assertRaises(Exception):
            cluster.write(bytes([1, 2, 3]))

        cluster.write(bytes([1, 2, 3, 4]))
        # offset=0 -> internal index 0; cluster[0:5] -> internal_data[0:10] = [1,2,3,4,FF,FF,FF,FF,FF,FF,FF,FF]
        self.assertEqual(bytes(cluster[0:6]), b'\x01\x02\x03\x04' + b'\xFF' * 8)

        cluster.write(bytes([4, 5, 6, 7]), offset=50)
        # offset=50 -> internal index 100; cluster[49:54] -> internal_data[98:108] = [FF,FF,4,5,6,7,FF,FF,FF,FF]
        self.assertEqual(bytes(cluster[49:54]), b'\xFF\xFF\x04\x05\x06\x07' + b'\xFF' * 4)

    def test_read_write_no_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=False)
        self.assertEqual(len(cluster), 100)
        self.assertEqual(cluster[10], b'\x00' * 2)        # 1 device byte = 2 python bytes
        self.assertEqual(cluster[10:20], b'\x00' * 20)
        self.assertEqual(cluster[50:], b'\x00' * 100)

        with self.assertRaises(IndexError):
            cluster[101]

        cluster.write(bytes([1, 2, 3, 4]))
        self.assertEqual(bytes(cluster[0:5]), b'\x00' * 10)

        cluster.write(bytes([4, 5, 6, 7]), offset=50)
        self.assertEqual(bytes(cluster[49:54]), b'\x00' * 10)

    def test_resize_with_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=True)
        cluster.shrink(50)
        self.assertEqual(len(cluster), 50)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 100)   # 50 device bytes = 100 python bytes

        cluster.extend(100, b'\xAA' * 100)                     # delta = 50 device bytes = 100 python bytes
        self.assertEqual(len(cluster), 100)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 100 + b'\xAA' * 100)

        cluster.extend(200)                                     # delta = 100 device bytes = 200 python zeros
        self.assertEqual(len(cluster), 200)
        self.assertEqual(bytes(cluster.data), b'\xFF' * 100 + b'\xAA' * 100 + b'\x00' * 200)

        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=True)
        with self.assertRaises(Exception):
            cluster.extend(101, bytes([1, 2, 3, 4]))                     # 1 extra byte

    def test_resize_no_data(self):
        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=False)
        cluster.shrink(50)
        self.assertEqual(len(cluster), 50)
        self.assertEqual(bytes(cluster.data), b'\x00' * 100)   # 50 device bytes = 100 python bytes

        cluster.extend(100, b'\xAA' * 100)                     # data ignored since has_data=False
        self.assertEqual(len(cluster), 100)
        self.assertEqual(bytes(cluster.data), b'\x00' * 200)   # 100 device bytes = 200 python bytes

        cluster.extend(1000)                                    # data not needed. No exception

        cluster = Cluster(start_addr=0x1000, size=100, char_bit=16, data=b'\xFF' * 200, has_data=True)
        with self.assertRaises(Exception):
            cluster.extend(101, bytes([1, 2, 3, 4]))            # 1 extra byte


class TestMemoryContent(ScrutinyUnitTest):
    def assert_clusters(self, clusters, args):
        self.assertEqual(len(clusters), len(args), str(clusters))

        for i in range(len(clusters)):
            self.assertEqual(clusters[i].start_addr, args[i][0], 'Cluster #%d' % i)
            self.assertEqual(clusters[i].size, args[i][1], 'Cluster #%d' % i)

    def test_read_write_basic(self):
        memcontent = MemoryContent()
        addr = 0x1234
        data = bytes(range(10))
        memcontent.write(addr, data)
        data2 = memcontent.read(addr, len(data))

        self.assertEqual(data, data2)

    def test_read_overflow(self):
        memcontent = MemoryContent()
        addr = 0x1234
        data = bytes(range(10))
        memcontent.write(addr, data)

        with self.assertRaises(Exception):
            memcontent.read(addr - 1, len(data))

        with self.assertRaises(Exception):
            memcontent.read(addr + 1, len(data))

    def test_merge_write(self):
        memcontent = MemoryContent()
        data = bytes(range(10))
        memcontent.write(0x1000, data)
        memcontent.write(0x1005, data)
        data2 = memcontent.read(0x1000, 15)
        self.assertEqual(data[0:5] + data, data2)

    def test_merge_write_limit_low_left(self):
        memcontent = MemoryContent()
        data = bytes(range(10))
        memcontent.write(1000, data)
        memcontent.write(990, data)
        data2 = memcontent.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_limit_high(self):
        memcontent = MemoryContent()
        data = bytes(range(10))
        memcontent.write(990, data)
        memcontent.write(1000, data)
        data2 = memcontent.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_middle(self):
        memcontent = MemoryContent()
        data1 = bytes(range(30))
        data2 = bytes(range(10))
        memcontent.write(1000, data1)
        memcontent.write(1010, data2)
        data3 = memcontent.read(1000, 30)
        self.assertEqual(data1[0:10] + data2 + data1[20:30], data3)

    def test_write_mutiple_overlap(self):
        memcontent = MemoryContent()
        data = bytes(range(10))
        memcontent.write(990, data)
        memcontent.write(1000, data)
        memcontent.write(1005, data)
        memcontent.write(800, data)
        memcontent.write(1100, data)
        memcontent.write(995, data)
        self.assertEqual(data, memcontent.read(800, len(data)))
        self.assertEqual(data, memcontent.read(1100, len(data)))
        data2 = memcontent.read(990, 25)
        self.assertEqual(data[0:5] + data + data, data2)

    def test_cluster_definition(self):
        memcontent = MemoryContent()
        data = bytes(range(10))
        memcontent.write(990, data)
        memcontent.write(1000, data)
        memcontent.write(1005, data)
        memcontent.write(800, data)
        memcontent.write(1100, data)
        memcontent.write(995, data)

        clusters = memcontent.get_cluster_list_no_data_by_address()  # Clusters should be sorted by address

        self.assert_clusters(clusters, [(800, 10), (990, 25), (1100, 10)])

    # ==== Deletion Test =======

    def delete_test_make_mem(self):
        memcontent = MemoryContent()
        data = bytes(range(0x100))
        memcontent.write(0x1000, data)
        memcontent.write(0x2000, data)
        memcontent.write(0x3000, data)

        return memcontent

    def test_delete_single_cluster_middle(self):
        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

    def test_delete_single_cluster_first(self):
        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

    def test_delete_single_cluster_last(self):
        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

    def test_delete_multiple_cluster(self):
        m = self.delete_test_make_mem()
        m.delete(0x2080, 0x1000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x80), (0x3080, 0x80)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x1000 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3001, 0x100 - 1)])

        m = self.delete_test_make_mem()
        m.delete(0x2080, 0x2000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x80)])

        m = self.delete_test_make_mem()
        m.delete(0, 0x4000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [])

    def test_delete_out_of_bounds(self):
        m = self.delete_test_make_mem()
        m.delete(0x4000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 0x100)])

    def test_write_delete_agglomerate_simple(self):
        m = MemoryContent()
        m.add_empty(0x1000, 0x100)
        m.delete(0x1080, 1)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x80), (0x1081, 0x7F)])
        m.add_empty(0x1080, 1)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x100)])

    def test_write_delete_agglomerate_complex(self):
        m = MemoryContent()
        m.add_empty(0x1000, 0x100)
        m.add_empty(0x1200, 0x100)
        m.add_empty(0x1400, 0x100)  # Will be deleted
        m.add_empty(0x1600, 0x100)  # Will be deleted
        m.add_empty(0x1800, 0x100)
        m.add_empty(0x2000, 0x100)

        m.delete(0x1300, 0x400)
        m.add_empty(0x1180, 0x80)
        m.add_empty(0x1900, 0x80)
        m.add_empty(0x1500, 0x100)

        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x100),
                             (0x1180, 0x180), (0x1500, 0x100), (0x1800, 0x180), (0x2000, 0x100)])
        m.add_empty(0x1000, 0x500)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x600), (0x1800, 0x180), (0x2000, 0x100)])

    def test_load_memdump(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'temp')
            with open(filename, 'w') as f:
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')
                f.write('0x00100010: 101112131415161718191a1b1c1d1e\n')
                f.write('0x00200000: 00112233445566778899')

            memcontent = MemoryContent(filename=filename)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 31), (0x00200000, 10)])

            # ====

            with open(filename, 'w') as f:
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')
                f.write('0x00100010: 101112131415161718191a1b1c1d1e\n')
                f.write('0x00200000: 00112233445566778899\n')   # Added a line feed here

            memcontent = MemoryContent(filename=filename)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 31), (0x00200000, 10)])

    def test_load_memdump_not_in_order(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'temp')
            with open(filename, 'w') as f:
                f.write('0x00100010: 101112131415161718191a1b1c1d1e\n')
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')
                f.write('0x00200000: 00112233445566778899')

            memcontent = MemoryContent(filename=filename)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 31), (0x00200000, 10)])


class TestMemoryContentCharBit16(ScrutinyUnitTest):
    def assert_clusters(self, clusters, args):
        self.assertEqual(len(clusters), len(args), str(clusters))

        for i in range(len(clusters)):
            self.assertEqual(clusters[i].start_addr, args[i][0], 'Cluster #%d' % i)
            self.assertEqual(clusters[i].size, args[i][1], 'Cluster #%d' % i)

    def test_read_write_basic(self):
        memcontent = MemoryContent(char_bit=16)
        addr = 0x1234
        data = bytes(range(10))          # 10 python bytes = 5 device bytes
        memcontent.write(addr, data)
        data2 = memcontent.read(addr, len(data) // 2)   # read 5 device bytes → 10 python bytes
        self.assertEqual(data, data2)

    def test_read_overflow(self):
        memcontent = MemoryContent(char_bit=16)
        addr = 0x1234
        len_bytes = 5
        data = bytes(range(len_bytes * 2))          # 10 python bytes = 5 device bytes
        memcontent.write(addr, data)

        with self.assertRaises(Exception):
            memcontent.read(addr - 1, len_bytes)   # before cluster start

        with self.assertRaises(Exception):
            memcontent.read(addr + 1, len_bytes)   # offset=1, size=5: 1+5=6 > 5

    def test_merge_write(self):
        memcontent = MemoryContent(char_bit=16)
        data = bytes(range(20))          # 20 python bytes = 10 device bytes
        memcontent.write(0x1000, data)   # cluster [0x1000, size=10]
        memcontent.write(0x1005, data)   # overlaps 5, extends 5 → [0x1000, size=15]
        data2 = memcontent.read(0x1000, 15)
        self.assertEqual(data[0:10] + data, data2)

    def test_merge_write_limit_low_left(self):
        memcontent = MemoryContent(char_bit=16)
        data = bytes(range(20))
        memcontent.write(1000, data)     # [1000, size=10]
        memcontent.write(990, data)      # [990, size=10], 990+10=1000 → adjacent → [990, size=20]
        data2 = memcontent.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_limit_high(self):
        memcontent = MemoryContent(char_bit=16)
        data = bytes(range(20))
        memcontent.write(990, data)      # [990, size=10]
        memcontent.write(1000, data)     # [1000, size=10], adjacent → [990, size=20]
        data2 = memcontent.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_middle(self):
        memcontent = MemoryContent(char_bit=16)
        data1 = bytes(range(60))         # 60 python bytes = 30 device bytes
        data2 = bytes(range(20))         # 20 python bytes = 10 device bytes
        memcontent.write(1000, data1)
        memcontent.write(1010, data2)    # overwrites device bytes 1010..1019
        data3 = memcontent.read(1000, 30)
        self.assertEqual(data1[0:20] + data2 + data1[40:60], data3)

    def test_write_mutiple_overlap(self):
        memcontent = MemoryContent(char_bit=16)
        byte_len = 10
        data = bytes(range(byte_len * 2))          # 20 python bytes = 10 device bytes
        memcontent.write(990, data)
        memcontent.write(1000, data)
        memcontent.write(1005, data)
        memcontent.write(800, data)
        memcontent.write(1100, data)
        memcontent.write(995, data)
        self.assertEqual(data, memcontent.read(800, byte_len))
        self.assertEqual(data, memcontent.read(1100, byte_len))
        data2 = memcontent.read(990, 25)
        self.assertEqual(data[0:10] + data + data, data2)

    def test_cluster_definition(self):
        memcontent = MemoryContent(char_bit=16)
        data = bytes(range(20))          # 20 python bytes = 10 device bytes
        memcontent.write(990, data)
        memcontent.write(1000, data)
        memcontent.write(1005, data)
        memcontent.write(800, data)
        memcontent.write(1100, data)
        memcontent.write(995, data)

        clusters = memcontent.get_cluster_list_no_data_by_address()

        self.assert_clusters(clusters, [(800, 10), (990, 25), (1100, 10)])

    # ==== Deletion Tests =======

    def delete_test_make_mem(self):
        memcontent = MemoryContent(char_bit=16)
        data = b'\xAA' * 0x200           # 0x200 python bytes = 0x100 device bytes
        memcontent.write(0x1000, data)
        memcontent.write(0x2000, data)
        memcontent.write(0x3000, data)
        return memcontent

    def test_delete_single_cluster_middle(self):
        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 1), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x20FF, 1), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3000, 0x100)])

    def test_delete_single_cluster_first(self):
        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 1), (0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x10FF, 1), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x1000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x2000, 0x100), (0x3000, 0x100)])

    def test_delete_single_cluster_last(self):
        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100 - 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 + 1, 0x100 - 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 1), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x30FF, 1)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100 + 1)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0x3000 - 1, 0x100 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100)])

    def test_delete_multiple_cluster(self):
        m = self.delete_test_make_mem()
        m.delete(0x2080, 0x1000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x80), (0x3080, 0x80)])

        m = self.delete_test_make_mem()
        m.delete(0x2000 - 1, 0x1000 + 2)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x3001, 0x100 - 1)])

        m = self.delete_test_make_mem()
        m.delete(0x2080, 0x2000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x80)])

        m = self.delete_test_make_mem()
        m.delete(0, 0x4000)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [])

    def test_delete_out_of_bounds(self):
        m = self.delete_test_make_mem()
        m.delete(0x4000, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 0x100)])

        m = self.delete_test_make_mem()
        m.delete(0, 0x100)
        clusters = m.get_cluster_list_no_data_by_address()
        self.assert_clusters(clusters, [(0x1000, 0x100), (0x2000, 0x100), (0x3000, 0x100)])

    def test_write_delete_agglomerate_simple(self):
        m = MemoryContent(char_bit=16)
        m.add_empty(0x1000, 0x100)
        m.delete(0x1080, 1)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x80), (0x1081, 0x7F)])
        m.add_empty(0x1080, 1)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x100)])

    def test_write_delete_agglomerate_complex(self):
        m = MemoryContent(char_bit=16)
        m.add_empty(0x1000, 0x100)
        m.add_empty(0x1200, 0x100)
        m.add_empty(0x1400, 0x100)  # Will be deleted
        m.add_empty(0x1600, 0x100)  # Will be deleted
        m.add_empty(0x1800, 0x100)
        m.add_empty(0x2000, 0x100)

        m.delete(0x1300, 0x400)
        m.add_empty(0x1180, 0x80)
        m.add_empty(0x1900, 0x80)
        m.add_empty(0x1500, 0x100)

        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x100),
                             (0x1180, 0x180), (0x1500, 0x100), (0x1800, 0x180), (0x2000, 0x100)])
        m.add_empty(0x1000, 0x500)
        self.assert_clusters(m.get_cluster_list_no_data_by_address(), [(0x1000, 0x600), (0x1800, 0x180), (0x2000, 0x100)])

    def test_load_memdump(self):
        # Hex strings must be multiples of 4 chars (= 1 device byte = 2 python bytes)
        # 32 chars = 8 device bytes; 16 chars = 4 device bytes
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'temp')
            with open(filename, 'w') as f:
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')   # 8 device bytes
                f.write('0x00100008: 101112131415161718191a1b1c1d1e1f\n')   # 8 device bytes, adjacent → merged
                f.write('0x00200000: 0011223344556677')                     # 4 device bytes

            memcontent = MemoryContent(filename=filename, char_bit=16)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 16), (0x00200000, 4)])

            # ====

            with open(filename, 'w') as f:
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')
                f.write('0x00100008: 101112131415161718191a1b1c1d1e1f\n')
                f.write('0x00200000: 0011223344556677\n')   # Added a line feed here

            memcontent = MemoryContent(filename=filename, char_bit=16)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 16), (0x00200000, 4)])

    def test_load_memdump_not_in_order(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'temp')
            with open(filename, 'w') as f:
                f.write('0x00100008: 101112131415161718191a1b1c1d1e1f\n')   # second block first
                f.write('0x00100000: 000102030405060708090a0b0c0d0e0f\n')   # first block second
                f.write('0x00200000: 0011223344556677')

            memcontent = MemoryContent(filename=filename, char_bit=16)
            self.assert_clusters(memcontent.get_cluster_list_no_data_by_address(), [(0x00100000, 16), (0x00200000, 4)])


if __name__ == '__main__':
    import unittest
    unittest.main()
