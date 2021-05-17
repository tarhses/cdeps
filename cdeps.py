import os
import re
import sys
import functools
from typing import Tuple, Set, Dict, Optional, Collection

SOURCE_EXTENSIONS = ['.c', '.cc', '.cp', '.cxx', '.cpp', '.c++', '.C']
HEADER_EXTENSIONS = ['.h', '.hpp']


class SourcePair:
    """Represent a C/C++ source file associated with its header.

    A SourcePair can also be an independent source (e.g. 'main.c') or header (e.g. macros or templates).
    """
    def __init__(self, source: Optional[str], header: Optional[str]):
        assert source is not None or header is not None
        self.source = source
        self.header = header
        self._internal_dependencies = None
        self._external_dependencies = None

    def __eq__(self, other):
        return self.source == other.source and self.header == other.header

    def __hash__(self):
        return hash((self.source, self.header))

    def __repr__(self):
        return f'SourcePair({self.source!r}, {self.header!r})'

    @property
    def has_source(self) -> bool:
        """Check whether the pair has a source file."""
        return self.source is not None

    @property
    def has_header(self) -> bool:
        """Check whether the pair has a header file."""
        return self.header is not None

    @property
    def name(self) -> str:
        """Return the pair's name i.e. its filename without extension."""
        if self.has_source:
            return remove_extension(self.source)
        else:
            assert self.has_header
            return remove_extension(self.header)

    @property
    def internal_dependencies(self) -> Set[str]:
        """Get the pair's internal dependencies. See :py:func:`get_dependencies_from_file`."""
        if self._internal_dependencies is None:
            self._resolve_dependencies()
        return self._internal_dependencies

    @property
    def external_dependencies(self) -> Set[str]:
        """Get the pair's external dependencies. See :py:func:`get_dependencies_from_file`."""
        if self._external_dependencies is None:
            self._resolve_dependencies()
        return self._external_dependencies

    def _resolve_dependencies(self):
        self._internal_dependencies = set()
        self._external_dependencies = set()
        if self.has_source:
            internal, external = get_dependencies_from_file(self.source)
            self._internal_dependencies.update(internal)
            self._external_dependencies.update(external)
        if self.has_header:
            internal, external = get_dependencies_from_file(self.header)
            self._internal_dependencies.update(internal)
            self._external_dependencies.update(external)


def get_dependencies_from_file(path: str) -> Tuple[Set[str], Set[str]]:
    """Return internal and external dependencies of a given C/C++ file.

    Internal dependencies are declared in '#include "..."' statements while external dependencies are
    in '#include <...>' statements.
    """
    internal = set()
    external = set()

    with open(path, 'r') as file:
        for line in file:
            internal_match = re.search(r'#\s*include\s*"(.*)"', line)
            external_match = re.search(r'#\s*include\s*<(.*)>', line)
            if internal_match is not None:
                internal.add(internal_match.group(1))
            if external_match is not None:
                external.add(external_match.group(1))

    return internal, external


def get_pairs_from_dir(base_dir: str) -> Set[SourcePair]:
    """Get every source pairs from a given directory."""
    sources, headers = get_sources_and_headers_from_dir(base_dir)
    return pair_sources_with_headers(sources, headers)


def get_sources_and_headers_from_dir(base_dir: str) -> Tuple[Set[str], Set[str]]:
    """Get every sources and headers from a given directory and return them as two separate sets."""
    sources = set()
    headers = set()

    base_dir = os.path.abspath(base_dir)
    for dirpath, _dirnames, names in os.walk(base_dir):
        for name in names:
            name = os.path.join(dirpath, name)
            if is_source(name):
                sources.add(name)
            elif is_header(name):
                headers.add(name)

    return sources, headers


def has_extension(path: str, extensions: Collection[str]) -> bool:
    """Check if a filename ends with one of given extensions.

    Examples:
    >>> has_extension('a.c', {'.c', '.cpp'})
    True
    >>> has_extension('a.c', {'.h'})
    False
    """
    for ext in extensions:
        if path.endswith(ext):
            return True
    return False


is_source = functools.partial(has_extension, extensions=SOURCE_EXTENSIONS)
is_header = functools.partial(has_extension, extensions=HEADER_EXTENSIONS)


def pair_sources_with_headers(sources: Collection[str], headers: Collection[str]) -> Set[SourcePair]:
    """Make source pairs from given sources and headers.

    Example:
    >>> pairs = pair_sources_with_headers({'a.cpp', 'b.cpp'}, {'b.h', 'c.h'})
    >>> pairs == {SourcePair('a.cpp', None), SourcePair('b.cpp', 'b.h'), SourcePair(None, 'c.h')}
    True
    """
    pairs = set()

    for source in sources:
        if header := find_corresponding_header(source, headers):
            pairs.add(SourcePair(source, header))
        else:
            pairs.add(SourcePair(source, None))

    for header in headers:
        if not find_corresponding_source(header, sources):
            pairs.add(SourcePair(None, header))

    return pairs


def find_corresponding_pair(path: str, pairs: Collection[str], extensions: Collection[str]) -> Optional[str]:
    """Return the corresponding pair of a filename if any, None otherwise.

    A pair is another filename with the same name but another extension.
    Tested extensions are given as a parameter.

    Example:
    >>> find_corresponding_pair('file.cpp', {'file.hpp'}, {'.h', '.hpp'})
    'file.hpp'
    """
    name = remove_extension(path)
    for ext in extensions:
        pair = f'{name}{ext}'
        if pair in pairs:
            return pair
    return None


find_corresponding_source = functools.partial(find_corresponding_pair, extensions=SOURCE_EXTENSIONS)
find_corresponding_header = functools.partial(find_corresponding_pair, extensions=HEADER_EXTENSIONS)


def map_dependencies_from_pairs(pairs: Set[SourcePair], include_dirs: Collection[str] = []) -> Dict[str, Set[str]]:
    """Make a dependency map from source pairs.

    The returned dict takes the following form:
    { 'unit1': { 'dependency1', 'dependency2', ... }, 'unit2': { ... }, ... }
    """
    units = {}

    for pair in pairs:
        unit = pair.name
        current_dir = os.path.dirname(unit)

        dependencies = set()
        for dependency in pair.internal_dependencies:
            try:
                dependency = resolve_include_path(dependency, current_dir, include_dirs)
            except FileNotFoundError as exc:
                print('warning:', exc)
                continue

            dependency = remove_extension(dependency)
            if unit != dependency:
                dependencies.add(dependency)

        for dependency in pair.external_dependencies:
            dependency = remove_extension(dependency)
            dependencies.add(dependency)

        units[unit] = dependencies

    return units


def resolve_include_path(name: str, current_dir: str, include_dirs: Collection[str] = []) -> str:
    """Resolve a C/C++ include path, trying current_dir first then include_dirs."""
    include_dirs = [current_dir] + include_dirs
    include_dirs = [os.path.abspath(dir) for dir in include_dirs]

    for include_dir in include_dirs:
        path = os.path.normpath(os.path.join(include_dir, name))
        if os.path.exists(path):
            return path

    raise FileNotFoundError(f'{name!r} not found in {include_dirs}')


def get_dependent_units(units: Dict[str, Collection[str]], dependencies: Collection[str]) -> Tuple[Set[str], Set[str]]:
    """Partition source units impacted and unimpacted by given dependencies.

    Example:
    >>> impacted, unimpacted = get_dependent_units(
    ...     {'a': {'b', 'c', 'd'}, 'b': {'c'}, 'c': {'e'}, 'd': set(), 'e': set()}, {'e'})
    >>> impacted == {'a', 'b', 'c', 'e'}
    True
    >>> unimpacted == {'d'}
    True
    """
    impacted = dependencies.copy()

    previous_length = 0
    while len(impacted) > previous_length:
        previous_length = len(impacted)
        found = set(unit for unit, deps in units.items() if deps.intersection(impacted))
        impacted.update(found)

    units_set = set(units)
    impacted.intersection_update(units_set)
    unimpacted = units_set - impacted
    return impacted, unimpacted


def remove_extension(path: str) -> str:
    """Remove the extension of a filename if any.

    Examples:
    >>> remove_extension('a.cpp')
    'a'
    >>> remove_extension('hello')
    'hello'
    """
    return os.path.splitext(path)[0]
