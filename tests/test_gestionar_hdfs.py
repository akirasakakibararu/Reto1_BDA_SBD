import hashlib
import unittest
from contextlib import contextmanager
from unittest.mock import Mock

from scripts.hdfs.gestionar_hdfs import _sha256_remote


class HdfsVerificationTests(unittest.TestCase):
    def test_hashes_chunks_returned_by_webhdfs_read(self) -> None:
        chunks = [b"original ", b"datos ", b"de prueba"]

        @contextmanager
        def read_chunks(path: str, chunk_size: int):
            self.assertEqual(path, "/user/test/dataset.csv")
            self.assertEqual(chunk_size, 1024 * 1024)
            yield iter(chunks)

        client = Mock()
        client.read.side_effect = read_chunks
        expected = hashlib.sha256(b"".join(chunks)).hexdigest()

        self.assertEqual(
            _sha256_remote(client, "/user/test/dataset.csv"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
