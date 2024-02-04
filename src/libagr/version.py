'''
Created on Feb 2, 2024

@author: boogie
'''
SEPS = [":", "-"]


class Version():
    def __init__(self, version):
        self.version = version
        version_str = version
        for c in SEPS:
            version_str = version_str.replace(c, ".")
        segments = []
        for segment in version_str.split("."):
            if segment.isdigit():
                segment = int(segment)
            segments.append(segment)
        self.segments = set(segments)

    def __str__(self):
        return self.version

    def compare(self, operator, version):
        if operator == "=":
            return self.segments == version.segmnets
        elif operator == ">":
            return self.segments > version.segments
        elif operator == ">=":
            return self.segments >= version.segments
        elif operator == "<=":
            return self.segments <= version.segments
        elif operator == "<":
            return self.segments < version.segments
        else:
            return False
