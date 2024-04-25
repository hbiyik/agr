'''
Created on Feb 2, 2024

@author: boogie
'''
import re
from libagr import defs


class Version():
    def __init__(self, version):
        self.version = version
        version_str = version
        for c in defs.VERSION_SEPS:
            version_str = version_str.replace(c, ".")
        segments = []
        for segment in version_str.split("."):
            if not segment.isdigit():
                # FIX-ME: This may not work always
                segment = re.sub(r"\D", "0", segment)
            if segment.isdigit():
                segment = int(segment)
                segments.append(segment)
        self.segments = segments

    def __str__(self):
        return self.version

    def __repr__(self):
        return self.version

    def compare(self, operator, version):
        if operator == defs.COMP_EQ:
            return self.segments == version.segments
        elif operator == defs.COMP_G:
            return self.segments > version.segments
        elif operator == defs.COMP_GE:
            return self.segments >= version.segments
        elif operator == defs.COMP_LE:
            return self.segments <= version.segments
        elif operator == defs.COMP_L:
            return self.segments < version.segments
        else:
            return False
