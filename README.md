# cdeps

This is a C/C++ static code analysis tool made to map dependencies. It can be used to inspect coupling between local dependencies. It simply works by opening source files and searching for "include" statements.

It was first made to analyse [qBittorrent's source code](https://github.com/qbittorrent/qBittorrent) but it could be used on other projects.

## Basic usage

Get source pairs from a directory. A source pair is a source file with its associated header file.

```python
>>> import cdeps
>>> pairs = cdeps.get_pairs_from_dir('src')
>>> pairs
{SourcePair('main.c', None), SourcePair('lib.c', 'lib.h')}
```

Make a dict associating source pairs with their direct dependencies.

```python
>>> units = cdeps.map_dependencies_from_pairs(pairs)
>>> units
{'main': {'lib', 'stdio'}, 'lib': {'string'}}
```

Find which source pairs directly or indirectly depend on a given dependency.

```python
>>> impacted, unimpacted = cdeps.get_dependent_units(units, {'string'})
>>> impacted
{'main', 'lib'}
>>> unimpacted
set()

>>> impacted, unimpacted = cdeps.get_dependent_units(units, {'stdio'})
>>> impacted
{'main'}
>>> unimpacted
{'lib'}
```

## Testing

To run the tests, you'll need [coverage.py](https://coverage.readthedocs.io).

```sh
pip install coverage
```

Then use the commands below. It will generate a coverage report in the "htmlcov/index.html" file.

```sh
# Check docstring examples
python3 -m doctest cdeps.py

# Run coverage testing
coverage run --branch -m unittest discover
coverage html
```

## License

The project is licensed under MIT. Feel free to use, copy, or modify it.

&copy; 2021, Pierre Luycx
