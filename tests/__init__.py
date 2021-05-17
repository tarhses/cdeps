#!/usr/bin/env python3

import unittest
import os

import cdeps


# To save some characters
def a(path: str) -> str:
    """Transform into an absolute path inside the sources directory (even if the file doesn't exist)."""
    return os.path.join(os.getcwd(), 'tests/sources', path)


# 'sources' directory structure:
# - README              (ignored)
# - main.c              (includes <stdio.h>, "a.h")
# - a.c                 (includes "a.h", "sub/b.h")
# - a.h                 (no includes)
# - sub/
#     - constants.h     (no includes)
#     - b.c             (includes <stdio.h>, "b.h", nonexistant "void.h")
#     - b.h             (includes "constants.h")


class TestCdeps(unittest.TestCase):

    def test_get_pairs_from_dir(self):
        pairs = cdeps.get_pairs_from_dir('tests/sources')
        expected = {
            cdeps.SourcePair(a('main.c'), None),
            cdeps.SourcePair(a('a.c'), a('a.h')),
            cdeps.SourcePair(a('sub/b.c'), a('sub/b.h')),
            cdeps.SourcePair(None, a('sub/constants.h')),
        }
        self.assertEqual(pairs, expected)

    def test_get_sources_and_headers_from_dir(self):
        sources, headers = cdeps.get_sources_and_headers_from_dir('tests/sources')
        expected_sources = {a('main.c'), a('a.c'), a('sub/b.c')}
        expected_headers = {a('a.h'), a('sub/b.h'), a('sub/constants.h')}
        self.assertEqual(sources, expected_sources)
        self.assertEqual(headers, expected_headers)

    def test_has_extension(self):
        result = cdeps.has_extension('main.cpp', ['.c', '.cpp'])
        self.assertTrue(result)

    def test_does_not_have_extension(self):
        result = cdeps.has_extension('library.h', ['.c', '.cc', '.C'])
        self.assertFalse(result)

    def test_find_corresponding_pair(self):
        pair = cdeps.find_corresponding_pair('hello.cpp', {'hi.h', 'hi.hpp', 'hello.h', 'goodbye.h'}, ['.h', '.hpp'])
        self.assertEqual(pair, 'hello.h')

    def test_does_not_find_corresponding_pair(self):
        pair = cdeps.find_corresponding_pair('hello.h', {'nope.c', 'nop.cpp', 'nada.cc'}, ['.c', '.cpp', '.cc'])
        self.assertIsNone(pair)

    def test_map_dependencies_from_pair(self):
        pairs = {cdeps.SourcePair(a('sub/b.c'), a('sub/b.h'))}
        units = cdeps.map_dependencies_from_pairs(pairs)
        expected = {a('sub/b'): {'stdio', a('sub/constants')}}
        self.assertEqual(units, expected)

    def test_map_dependencies_from_pair_without_header(self):
        pairs = {cdeps.SourcePair(a('main.c'), None)}
        units = cdeps.map_dependencies_from_pairs(pairs)
        expected = {a('main'): {'stdio', a('a')}}
        self.assertEqual(units, expected)

    def test_map_no_dependencies_from_pair(self):
        pairs = {cdeps.SourcePair(None, a('sub/constants.h'))}
        units = cdeps.map_dependencies_from_pairs(pairs)
        expected = {a('sub/constants'): set()}
        self.assertEqual(units, expected)

    def test_resolve_include_root_path(self):
        path = cdeps.resolve_include_path('a.h', 'tests/sources')
        expected = a('a.h')
        self.assertEqual(path, expected)

    def test_resolve_include_sub_path(self):
        path = cdeps.resolve_include_path('sub/b.h', 'tests/sources')
        expected = a('sub/b.h')
        self.assertEqual(path, expected)

    def test_resolve_include_default_path(self):
        path = cdeps.resolve_include_path('b.h', 'tests/sources', ['tests/sources/sub'])
        expected = a('sub/b.h')
        self.assertEqual(path, expected)

    def test_resolve_include_nonexistent_path(self):
        with self.assertRaises(FileNotFoundError):
            cdeps.resolve_include_path('void.h', 'tests/sources/sub', ['tests/sources'])

    def test_get_dependent_units(self):
        units = {
            'main': {'stdio', 'a'},
            'a': {'b'},
            'sub/constants': set(),
            'sub/b': {'sub/constants', 'stdio'},
        }
        impacted, unimpacted = cdeps.get_dependent_units(units, {'stdio'})
        expected_impacted = {'main', 'sub/b'}
        expected_unimpacted = {'a', 'sub/constants'}
        self.assertEqual(impacted, expected_impacted)
        self.assertEqual(unimpacted, expected_unimpacted)

    def test_get_no_dependent_units(self):
        units = {
            'main': {'a', 'b'},
            'a': set(),
            'b': {'a'},
        }
        impacted, unimpacted = cdeps.get_dependent_units(units, {'hello', 'hi'})
        expected_impacted = set()
        expected_unimpacted = {'main', 'a', 'b'}
        self.assertEqual(impacted, expected_impacted)
        self.assertEqual(unimpacted, expected_unimpacted)

    def test_get_independent_units(self):
        units = {
            'main': {'a'},
            'a': set(),
        }
        impacted, unimpacted = cdeps.get_dependent_units(units, set())
        expected_impacted = set()
        expected_unimpacted = {'main', 'a'}
        self.assertEqual(impacted, expected_impacted)
        self.assertEqual(unimpacted, expected_unimpacted)

    def test_remove_extension_from_file(self):
        name = cdeps.remove_extension('hello.txt')
        self.assertEqual(name, 'hello')

    def test_remove_extension_from_path(self):
        path = cdeps.remove_extension('a/b/c/d.ini')
        self.assertEqual(path, 'a/b/c/d')

    def test_remove_nonexistent_extension(self):
        name = cdeps.remove_extension('test')
        self.assertEqual(name, 'test')


if __name__ == '__main__':
    unittest.main()
