# -*- coding: utf-8 -*-


"""
Kickstart syntax is extended with:

%fulltree-excludes
<srpm_name>
<srpm_name>
...
%end

Fulltree excludes allow us to define SRPM names
we don't want to be part of fulltree processing.
"""


import pykickstart.parser
import pykickstart.sections


class FulltreeExcludesSection(pykickstart.sections.Section):
    sectionOpen = "%fulltree-excludes"

    def handleLine(self, line):
        if not self.handler:
            return

        (h, s, t) = line.partition('#')
        line = h.rstrip()

        self.handler.fulltree_excludes.add(line)


class MultilibBlacklistSection(pykickstart.sections.Section):
    sectionOpen = "%multilib-blacklist"

    def handleLine(self, line):
        if not self.handler:
            return

        (h, s, t) = line.partition('#')
        line = h.rstrip()

        self.handler.multilib_blacklist.add(line)


class MultilibWhitelistSection(pykickstart.sections.Section):
    sectionOpen = "%multilib-whitelist"

    def handleLine(self, line):
        if not self.handler:
            return

        (h, s, t) = line.partition('#')
        line = h.rstrip()

        self.handler.multilib_whitelist.add(line)


class KickstartParser(pykickstart.parser.KickstartParser):
    def setupSections(self):
        pykickstart.parser.KickstartParser.setupSections(self)
        self.registerSection(FulltreeExcludesSection(self.handler))
        self.registerSection(MultilibBlacklistSection(self.handler))
        self.registerSection(MultilibWhitelistSection(self.handler))


HandlerClass = pykickstart.version.returnClassForVersion()
class PungiHandler(HandlerClass):
    def __init__(self, *args, **kwargs):
        HandlerClass.__init__(self, *args, **kwargs)
        self.fulltree_excludes = set()
        self.multilib_blacklist = set()
        self.multilib_whitelist = set()


def get_ksparser(ks_path=None):
    """
    Return a kickstart parser instance.
    Read kickstart if ks_path provided.
    """
    ksparser = KickstartParser(PungiHandler())
    if ks_path:
        ksparser.readKickstart(ks_path)
    return ksparser
