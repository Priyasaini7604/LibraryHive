#!/usr/bin/env python
"""Django's command-line utility.

Settings default to config.settings.local, and to config.settings.test when
running the test suite. DJANGO_SETTINGS_MODULE always takes precedence.
"""

import os
import sys


def main():
    default = "config.settings.test" if len(sys.argv) > 1 and sys.argv[1] == "test" else "config.settings.local"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default)
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
