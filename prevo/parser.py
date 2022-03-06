"""Command line parser"""

# ----------------------------- License information --------------------------

# This file is part of the prevo python package.
# Copyright (C) 2022 Olivier Vincent

# The prevo package is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The prevo package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with the prevo python package.
# If not, see <https://www.gnu.org/licenses/>


import argparse


def parse_function(functions, description='', default_function=None):
    """Trigger a function with arguments from command line.

    Parameters
    ----------
    - functions: dict {name: function} (name is used in the CLI to refer
                 to the function and can be the function full name or a
                 shortcut)
    - description: any specific description of functions/arguments to add
                   to the default commmand line parser help
    - default_function: name of the function (functions dict key) that is
                        triggered if no function name is given (optional).
    """

    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.RawTextHelpFormatter)

    # The nargs='?' is to have a positional argument with a default value
    msg_func = f"\nFunction to trigger.\nAvailable: {', '.join(functions)}."
    add_kwargs = {}
    if default_function is not None:
        msg_func += f"\nDefault: {default_function}."
        add_kwargs['default'] = default_function

    parser.add_argument('function', type=str, nargs='?', help=msg_func, **add_kwargs)

    msg_args = '\nArgs/kwargs of function.\nNo quotes required around str.'
    msg_args += "\nOther types inferred.\nExample foo a=hello for foo(a='hello')"
    parser.add_argument('arguments', type=str, nargs='*', help=msg_args)

    parsed = parser.parse_args()

    args = []
    kwargs = {}
    for argument in parsed.arguments:
        raw_arg = argument.split('=')
        try:
            k, v = raw_arg
        except ValueError:
            a, = raw_arg
            try:
                # Avoids having to explicily put type
                exec(f"args.append({a})")
            except NameError:
                # In case of strings, use the input as the string itself
                args.append(a)
        else:
            try:
                # Same strategy as above
                exec(f"kwargs['{k}'] = {v}")
            except NameError:
                kwargs[k] = v

    return functions[parsed.function](*args, **kwargs)
