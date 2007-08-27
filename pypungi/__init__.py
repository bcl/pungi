#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import logging
import os
import subprocess

class PungiBase():
    """The base Pungi class.  Set up config items and logging here"""

    def __init__(self, config):
        self.config = config

        self.doLoggerSetup()

        self.workdir = os.path.join(self.config.get('default', 'destdir'),
                                    'work',
                                    self.config.get('default', 'flavor'),
                                    self.config.get('default', 'arch'))



    def doLoggerSetup(self):
        """Setup our logger"""

        logdir = os.path.join(self.config.get('default', 'destdir'), 'logs')

        if not os.path.exists(logdir):
            os.makedirs(logdir)

        if self.config.get('default', 'flavor'):
            logfile = os.path.join(logdir, '%s.%s.log' % (self.config.get('default', 'flavor'),
                                                          self.config.get('default', 'arch')))
        else:
            logfile = os.path.join(logdir, '%s.log' % (self.config.get('default', 'arch')))

        # Create the root logger, that will log to our file
        logging.basicConfig(level=logging.DEBUG,
                            format='%(name)s.%(levelname)s: %(message)s',
                            filename=logfile)


def _doRunCommand(command, logger, rundir='/tmp', output=subprocess.PIPE, error=subprocess.PIPE):
    """Run a command and log the output.  Error out if we get something on stderr"""


    logger.info("Running %s" % ' '.join(command))

    p1 = subprocess.Popen(command, cwd=rundir, stdout=output, stderr=error, universal_newlines=True)
    (out, err) = p1.communicate()

    if out:
        logger.debug(out)

    if p1.returncode != 0:
        logger.error("Got an error from %s" % command[0])
        logger.error(err)
        raise OSError, "Got an error from %s: %s" % (command[0], err)

