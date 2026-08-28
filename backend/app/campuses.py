from enum import Enum


class Campus(str, Enum):
    qingchun = "庆春"
    qiantang = "钱塘"
    grand_canal = "大运河"
    shaoxing = "绍兴"


DEFAULT_CAMPUS = Campus.qingchun
CAMPUS_VALUES = tuple(campus.value for campus in Campus)
