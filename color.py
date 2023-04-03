import colorsys
from math import sqrt, log10
from pynecone.var import BaseVar
from typing import Any

colors = {}

# Color Presets
ALICEBLUE = (240, 248, 255)
ANTIQUEWHITE = (250, 235, 215)
ANTIQUEWHITE1 = (255, 239, 219)
ANTIQUEWHITE2 = (238, 223, 204)
ANTIQUEWHITE3 = (205, 192, 176)
ANTIQUEWHITE4 = (139, 131, 120)
AQUA = (0, 255, 255)
AQUAMARINE1 = (127, 255, 212)
AQUAMARINE2 = (118, 238, 198)
AQUAMARINE3 = (102, 205, 170)
AQUAMARINE4 = (69, 139, 116)
AZURE1 = (240, 255, 255)
AZURE2 = (224, 238, 238)
AZURE3 = (193, 205, 205)
AZURE4 = (131, 139, 139)
BANANA = (227, 207, 87)
BEIGE = (245, 245, 220)
BISQUE1 = (255, 228, 196)
BISQUE2 = (238, 213, 183)
BISQUE3 = (205, 183, 158)
BISQUE4 = (139, 125, 107)
BLACK = (0, 0, 0)
BLANCHEDALMOND = (255, 235, 205)
BLUE = (0, 0, 255)
BLUE2 = (0, 0, 238)
BLUE3 = (0, 0, 205)
BLUE4 = (0, 0, 139)
BLUEVIOLET = (138, 43, 226)
BRICK = (156, 102, 31)
BROWN = (165, 42, 42)
BROWN1 = (255, 64, 64)
BROWN2 = (238, 59, 59)
BROWN3 = (205, 51, 51)
BROWN4 = (139, 35, 35)
BURLYWOOD = (222, 184, 135)
BURLYWOOD1 = (255, 211, 155)
BURLYWOOD2 = (238, 197, 145)
BURLYWOOD3 = (205, 170, 125)
BURLYWOOD4 = (139, 115, 85)
BURNTSIENNA = (138, 54, 15)
BURNTUMBER = (138, 51, 36)
CADETBLUE = (95, 158, 160)
CADETBLUE1 = (152, 245, 255)
CADETBLUE2 = (142, 229, 238)
CADETBLUE3 = (122, 197, 205)
CADETBLUE4 = (83, 134, 139)
CADMIUMORANGE = (255, 97, 3)
CADMIUMYELLOW = (255, 153, 18)
CARROT = (237, 145, 33)
CHARTREUSE1 = (127, 255, 0)
CHARTREUSE2 = (118, 238, 0)
CHARTREUSE3 = (102, 205, 0)
CHARTREUSE4 = (69, 139, 0)
CHOCOLATE = (210, 105, 30)
CHOCOLATE1 = (255, 127, 36)
CHOCOLATE2 = (238, 118, 33)
CHOCOLATE3 = (205, 102, 29)
CHOCOLATE4 = (139, 69, 19)
COBALT = (61, 89, 171)
COBALTGREEN = (61, 145, 64)
COLDGREY = (128, 138, 135)
CORAL = (255, 127, 80)
CORAL1 = (255, 114, 86)
CORAL2 = (238, 106, 80)
CORAL3 = (205, 91, 69)
CORAL4 = (139, 62, 47)
CORNFLOWERBLUE = (100, 149, 237)
CORNSILK1 = (255, 248, 220)
CORNSILK2 = (238, 232, 205)
CORNSILK3 = (205, 200, 177)
CORNSILK4 = (139, 136, 120)
CRIMSON = (220, 20, 60)
CYAN2 = (0, 238, 238)
CYAN3 = (0, 205, 205)
CYAN4 = (0, 139, 139)
DARKGOLDENROD = (184, 134, 11)
DARKGOLDENROD1 = (255, 185, 15)
DARKGOLDENROD2 = (238, 173, 14)
DARKGOLDENROD3 = (205, 149, 12)
DARKGOLDENROD4 = (139, 101, 8)
DARKGRAY = (169, 169, 169)
DARKGREEN = (0, 100, 0)
DARKKHAKI = (189, 183, 107)
DARKOLIVEGREEN = (85, 107, 47)
DARKOLIVEGREEN1 = (202, 255, 112)
DARKOLIVEGREEN2 = (188, 238, 104)
DARKOLIVEGREEN3 = (162, 205, 90)
DARKOLIVEGREEN4 = (110, 139, 61)
DARKORANGE = (255, 140, 0)
DARKORANGE1 = (255, 127, 0)
DARKORANGE2 = (238, 118, 0)
DARKORANGE3 = (205, 102, 0)
DARKORANGE4 = (139, 69, 0)
DARKORCHID = (153, 50, 204)
DARKORCHID1 = (191, 62, 255)
DARKORCHID2 = (178, 58, 238)
DARKORCHID3 = (154, 50, 205)
DARKORCHID4 = (104, 34, 139)
DARKSALMON = (233, 150, 122)
DARKSEAGREEN = (143, 188, 143)
DARKSEAGREEN1 = (193, 255, 193)
DARKSEAGREEN2 = (180, 238, 180)
DARKSEAGREEN3 = (155, 205, 155)
DARKSEAGREEN4 = (105, 139, 105)
DARKSLATEBLUE = (72, 61, 139)
DARKSLATEGRAY = (47, 79, 79)
DARKSLATEGRAY1 = (151, 255, 255)
DARKSLATEGRAY2 = (141, 238, 238)
DARKSLATEGRAY3 = (121, 205, 205)
DARKSLATEGRAY4 = (82, 139, 139)
DARKTURQUOISE = (0, 206, 209)
DARKVIOLET = (148, 0, 211)
DEEPPINK1 = (255, 20, 147)
DEEPPINK2 = (238, 18, 137)
DEEPPINK3 = (205, 16, 118)
DEEPPINK4 = (139, 10, 80)
DEEPSKYBLUE1 = (0, 191, 255)
DEEPSKYBLUE2 = (0, 178, 238)
DEEPSKYBLUE3 = (0, 154, 205)
DEEPSKYBLUE4 = (0, 104, 139)
DIMGRAY = (105, 105, 105)
DIMGRAY = (105, 105, 105)
DODGERBLUE1 = (30, 144, 255)
DODGERBLUE2 = (28, 134, 238)
DODGERBLUE3 = (24, 116, 205)
DODGERBLUE4 = (16, 78, 139)
EGGSHELL = (252, 230, 201)
EMERALDGREEN = (0, 201, 87)
FIREBRICK = (178, 34, 34)
FIREBRICK1 = (255, 48, 48)
FIREBRICK2 = (238, 44, 44)
FIREBRICK3 = (205, 38, 38)
FIREBRICK4 = (139, 26, 26)
FLESH = (255, 125, 64)
FLORALWHITE = (255, 250, 240)
FORESTGREEN = (34, 139, 34)
GAINSBORO = (220, 220, 220)
GHOSTWHITE = (248, 248, 255)
GOLD1 = (255, 215, 0)
GOLD2 = (238, 201, 0)
GOLD3 = (205, 173, 0)
GOLD4 = (139, 117, 0)
GOLDENROD = (218, 165, 32)
GOLDENROD1 = (255, 193, 37)
GOLDENROD2 = (238, 180, 34)
GOLDENROD3 = (205, 155, 29)
GOLDENROD4 = (139, 105, 20)
GRAY = (128, 128, 128)
GRAY1 = (3, 3, 3)
GRAY10 = (26, 26, 26)
GRAY11 = (28, 28, 28)
GRAY12 = (31, 31, 31)
GRAY13 = (33, 33, 33)
GRAY14 = (36, 36, 36)
GRAY15 = (38, 38, 38)
GRAY16 = (41, 41, 41)
GRAY17 = (43, 43, 43)
GRAY18 = (46, 46, 46)
GRAY19 = (48, 48, 48)
GRAY2 = (5, 5, 5)
GRAY20 = (51, 51, 51)
GRAY21 = (54, 54, 54)
GRAY22 = (56, 56, 56)
GRAY23 = (59, 59, 59)
GRAY24 = (61, 61, 61)
GRAY25 = (64, 64, 64)
GRAY26 = (66, 66, 66)
GRAY27 = (69, 69, 69)
GRAY28 = (71, 71, 71)
GRAY29 = (74, 74, 74)
GRAY3 = (8, 8, 8)
GRAY30 = (77, 77, 77)
GRAY31 = (79, 79, 79)
GRAY32 = (82, 82, 82)
GRAY33 = (84, 84, 84)
GRAY34 = (87, 87, 87)
GRAY35 = (89, 89, 89)
GRAY36 = (92, 92, 92)
GRAY37 = (94, 94, 94)
GRAY38 = (97, 97, 97)
GRAY39 = (99, 99, 99)
GRAY4 = (10, 10, 10)
GRAY40 = (102, 102, 102)
GRAY42 = (107, 107, 107)
GRAY43 = (110, 110, 110)
GRAY44 = (112, 112, 112)
GRAY45 = (115, 115, 115)
GRAY46 = (117, 117, 117)
GRAY47 = (120, 120, 120)
GRAY48 = (122, 122, 122)
GRAY49 = (125, 125, 125)
GRAY5 = (13, 13, 13)
GRAY50 = (127, 127, 127)
GRAY51 = (130, 130, 130)
GRAY52 = (133, 133, 133)
GRAY53 = (135, 135, 135)
GRAY54 = (138, 138, 138)
GRAY55 = (140, 140, 140)
GRAY56 = (143, 143, 143)
GRAY57 = (145, 145, 145)
GRAY58 = (148, 148, 148)
GRAY59 = (150, 150, 150)
GRAY6 = (15, 15, 15)
GRAY60 = (153, 153, 153)
GRAY61 = (156, 156, 156)
GRAY62 = (158, 158, 158)
GRAY63 = (161, 161, 161)
GRAY64 = (163, 163, 163)
GRAY65 = (166, 166, 166)
GRAY66 = (168, 168, 168)
GRAY67 = (171, 171, 171)
GRAY68 = (173, 173, 173)
GRAY69 = (176, 176, 176)
GRAY7 = (18, 18, 18)
GRAY70 = (179, 179, 179)
GRAY71 = (181, 181, 181)
GRAY72 = (184, 184, 184)
GRAY73 = (186, 186, 186)
GRAY74 = (189, 189, 189)
GRAY75 = (191, 191, 191)
GRAY76 = (194, 194, 194)
GRAY77 = (196, 196, 196)
GRAY78 = (199, 199, 199)
GRAY79 = (201, 201, 201)
GRAY8 = (20, 20, 20)
GRAY80 = (204, 204, 204)
GRAY81 = (207, 207, 207)
GRAY82 = (209, 209, 209)
GRAY83 = (212, 212, 212)
GRAY84 = (214, 214, 214)
GRAY85 = (217, 217, 217)
GRAY86 = (219, 219, 219)
GRAY87 = (222, 222, 222)
GRAY88 = (224, 224, 224)
GRAY89 = (227, 227, 227)
GRAY9 = (23, 23, 23)
GRAY90 = (229, 229, 229)
GRAY91 = (232, 232, 232)
GRAY92 = (235, 235, 235)
GRAY93 = (237, 237, 237)
GRAY94 = (240, 240, 240)
GRAY95 = (242, 242, 242)
GRAY97 = (247, 247, 247)
GRAY98 = (250, 250, 250)
GRAY99 = (252, 252, 252)
GREEN = (0, 128, 0)
GREEN1 = (0, 255, 0)
GREEN2 = (0, 238, 0)
GREEN3 = (0, 205, 0)
GREEN4 = (0, 139, 0)
GREENYELLOW = (173, 255, 47)
HONEYDEW1 = (240, 255, 240)
HONEYDEW2 = (224, 238, 224)
HONEYDEW3 = (193, 205, 193)
HONEYDEW4 = (131, 139, 131)
HOTPINK = (255, 105, 180)
HOTPINK1 = (255, 110, 180)
HOTPINK2 = (238, 106, 167)
HOTPINK3 = (205, 96, 144)
HOTPINK4 = (139, 58, 98)
INDIANRED = (176, 23, 31)
INDIANRED = (205, 92, 92)
INDIANRED1 = (255, 106, 106)
INDIANRED2 = (238, 99, 99)
INDIANRED3 = (205, 85, 85)
INDIANRED4 = (139, 58, 58)
INDIGO = (75, 0, 130)
IVORY1 = (255, 255, 240)
IVORY2 = (238, 238, 224)
IVORY3 = (205, 205, 193)
IVORY4 = (139, 139, 131)
IVORYBLACK = (41, 36, 33)
KHAKI = (240, 230, 140)
KHAKI1 = (255, 246, 143)
KHAKI2 = (238, 230, 133)
KHAKI3 = (205, 198, 115)
KHAKI4 = (139, 134, 78)
LAVENDER = (230, 230, 250)
LAVENDERBLUSH1 = (255, 240, 245)
LAVENDERBLUSH2 = (238, 224, 229)
LAVENDERBLUSH3 = (205, 193, 197)
LAVENDERBLUSH4 = (139, 131, 134)
LAWNGREEN = (124, 252, 0)
LEMONCHIFFON1 = (255, 250, 205)
LEMONCHIFFON2 = (238, 233, 191)
LEMONCHIFFON3 = (205, 201, 165)
LEMONCHIFFON4 = (139, 137, 112)
LIGHTBLUE = (173, 216, 230)
LIGHTBLUE1 = (191, 239, 255)
LIGHTBLUE2 = (178, 223, 238)
LIGHTBLUE3 = (154, 192, 205)
LIGHTBLUE4 = (104, 131, 139)
LIGHTCORAL = (240, 128, 128)
LIGHTCYAN1 = (224, 255, 255)
LIGHTCYAN2 = (209, 238, 238)
LIGHTCYAN3 = (180, 205, 205)
LIGHTCYAN4 = (122, 139, 139)
LIGHTGOLDENROD1 = (255, 236, 139)
LIGHTGOLDENROD2 = (238, 220, 130)
LIGHTGOLDENROD3 = (205, 190, 112)
LIGHTGOLDENROD4 = (139, 129, 76)
LIGHTGOLDENRODYELLOW = (250, 250, 210)
LIGHTGREY = (211, 211, 211)
LIGHTPINK = (255, 182, 193)
LIGHTPINK1 = (255, 174, 185)
LIGHTPINK2 = (238, 162, 173)
LIGHTPINK3 = (205, 140, 149)
LIGHTPINK4 = (139, 95, 101)
LIGHTSALMON1 = (255, 160, 122)
LIGHTSALMON2 = (238, 149, 114)
LIGHTSALMON3 = (205, 129, 98)
LIGHTSALMON4 = (139, 87, 66)
LIGHTSEAGREEN = (32, 178, 170)
LIGHTSKYBLUE = (135, 206, 250)
LIGHTSKYBLUE1 = (176, 226, 255)
LIGHTSKYBLUE2 = (164, 211, 238)
LIGHTSKYBLUE3 = (141, 182, 205)
LIGHTSKYBLUE4 = (96, 123, 139)
LIGHTSLATEBLUE = (132, 112, 255)
LIGHTSLATEGRAY = (119, 136, 153)
LIGHTSTEELBLUE = (176, 196, 222)
LIGHTSTEELBLUE1 = (202, 225, 255)
LIGHTSTEELBLUE2 = (188, 210, 238)
LIGHTSTEELBLUE3 = (162, 181, 205)
LIGHTSTEELBLUE4 = (110, 123, 139)
LIGHTYELLOW1 = (255, 255, 224)
LIGHTYELLOW2 = (238, 238, 209)
LIGHTYELLOW3 = (205, 205, 180)
LIGHTYELLOW4 = (139, 139, 122)
LIMEGREEN = (50, 205, 50)
LINEN = (250, 240, 230)
MAGENTA = (255, 0, 255)
MAGENTA2 = (238, 0, 238)
MAGENTA3 = (205, 0, 205)
MAGENTA4 = (139, 0, 139)
MANGANESEBLUE = (3, 168, 158)
MAROON = (128, 0, 0)
MAROON1 = (255, 52, 179)
MAROON2 = (238, 48, 167)
MAROON3 = (205, 41, 144)
MAROON4 = (139, 28, 98)
MEDIUMORCHID = (186, 85, 211)
MEDIUMORCHID1 = (224, 102, 255)
MEDIUMORCHID2 = (209, 95, 238)
MEDIUMORCHID3 = (180, 82, 205)
MEDIUMORCHID4 = (122, 55, 139)
MEDIUMPURPLE = (147, 112, 219)
MEDIUMPURPLE1 = (171, 130, 255)
MEDIUMPURPLE2 = (159, 121, 238)
MEDIUMPURPLE3 = (137, 104, 205)
MEDIUMPURPLE4 = (93, 71, 139)
MEDIUMSEAGREEN = (60, 179, 113)
MEDIUMSLATEBLUE = (123, 104, 238)
MEDIUMSPRINGGREEN = (0, 250, 154)
MEDIUMTURQUOISE = (72, 209, 204)
MEDIUMVIOLETRED = (199, 21, 133)
MELON = (227, 168, 105)
MIDNIGHTBLUE = (25, 25, 112)
MINT = (189, 252, 201)
MINTCREAM = (245, 255, 250)
MISTYROSE1 = (255, 228, 225)
MISTYROSE2 = (238, 213, 210)
MISTYROSE3 = (205, 183, 181)
MISTYROSE4 = (139, 125, 123)
MOCCASIN = (255, 228, 181)
NAVAJOWHITE1 = (255, 222, 173)
NAVAJOWHITE2 = (238, 207, 161)
NAVAJOWHITE3 = (205, 179, 139)
NAVAJOWHITE4 = (139, 121, 94)
NAVY = (0, 0, 128)
OLDLACE = (253, 245, 230)
OLIVE = (128, 128, 0)
OLIVEDRAB = (107, 142, 35)
OLIVEDRAB1 = (192, 255, 62)
OLIVEDRAB2 = (179, 238, 58)
OLIVEDRAB3 = (154, 205, 50)
OLIVEDRAB4 = (105, 139, 34)
ORANGE = (255, 128, 0)
ORANGE1 = (255, 165, 0)
ORANGE2 = (238, 154, 0)
ORANGE3 = (205, 133, 0)
ORANGE4 = (139, 90, 0)
ORANGERED1 = (255, 69, 0)
ORANGERED2 = (238, 64, 0)
ORANGERED3 = (205, 55, 0)
ORANGERED4 = (139, 37, 0)
ORCHID = (218, 112, 214)
ORCHID1 = (255, 131, 250)
ORCHID2 = (238, 122, 233)
ORCHID3 = (205, 105, 201)
ORCHID4 = (139, 71, 137)
PALEGOLDENROD = (238, 232, 170)
PALEGREEN = (152, 251, 152)
PALEGREEN1 = (154, 255, 154)
PALEGREEN2 = (144, 238, 144)
PALEGREEN3 = (124, 205, 124)
PALEGREEN4 = (84, 139, 84)
PALETURQUOISE1 = (187, 255, 255)
PALETURQUOISE2 = (174, 238, 238)
PALETURQUOISE3 = (150, 205, 205)
PALETURQUOISE4 = (102, 139, 139)
PALEVIOLETRED = (219, 112, 147)
PALEVIOLETRED1 = (255, 130, 171)
PALEVIOLETRED2 = (238, 121, 159)
PALEVIOLETRED3 = (205, 104, 137)
PALEVIOLETRED4 = (139, 71, 93)
PAPAYAWHIP = (255, 239, 213)
PEACHPUFF1 = (255, 218, 185)
PEACHPUFF2 = (238, 203, 173)
PEACHPUFF3 = (205, 175, 149)
PEACHPUFF4 = (139, 119, 101)
PEACOCK = (51, 161, 201)
PINK = (255, 192, 203)
PINK1 = (255, 181, 197)
PINK2 = (238, 169, 184)
PINK3 = (205, 145, 158)
PINK4 = (139, 99, 108)
PLUM = (221, 160, 221)
PLUM1 = (255, 187, 255)
PLUM2 = (238, 174, 238)
PLUM3 = (205, 150, 205)
PLUM4 = (139, 102, 139)
POWDERBLUE = (176, 224, 230)
PURPLE = (128, 0, 128)
PURPLE1 = (155, 48, 255)
PURPLE2 = (145, 44, 238)
PURPLE3 = (125, 38, 205)
PURPLE4 = (85, 26, 139)
RASPBERRY = (135, 38, 87)
RAWSIENNA = (199, 97, 20)
RED1 = (255, 0, 0)
RED2 = (238, 0, 0)
RED3 = (205, 0, 0)
RED4 = (139, 0, 0)
ROSYBROWN = (188, 143, 143)
ROSYBROWN1 = (255, 193, 193)
ROSYBROWN2 = (238, 180, 180)
ROSYBROWN3 = (205, 155, 155)
ROSYBROWN4 = (139, 105, 105)
ROYALBLUE = (65, 105, 225)
ROYALBLUE1 = (72, 118, 255)
ROYALBLUE2 = (67, 110, 238)
ROYALBLUE3 = (58, 95, 205)
ROYALBLUE4 = (39, 64, 139)
SALMON = (250, 128, 114)
SALMON1 = (255, 140, 105)
SALMON2 = (238, 130, 98)
SALMON3 = (205, 112, 84)
SALMON4 = (139, 76, 57)
SANDYBROWN = (244, 164, 96)
SAPGREEN = (48, 128, 20)
SEAGREEN1 = (84, 255, 159)
SEAGREEN2 = (78, 238, 148)
SEAGREEN3 = (67, 205, 128)
SEAGREEN4 = (46, 139, 87)
SEASHELL1 = (255, 245, 238)
SEASHELL2 = (238, 229, 222)
SEASHELL3 = (205, 197, 191)
SEASHELL4 = (139, 134, 130)
SEPIA = (94, 38, 18)
SGIBEET = (142, 56, 142)
SGIBRIGHTGRAY = (197, 193, 170)
SGICHARTREUSE = (113, 198, 113)
SGIDARKGRAY = (85, 85, 85)
SGIGRAY12 = (30, 30, 30)
SGIGRAY16 = (40, 40, 40)
SGIGRAY32 = (81, 81, 81)
SGIGRAY36 = (91, 91, 91)
SGIGRAY52 = (132, 132, 132)
SGIGRAY56 = (142, 142, 142)
SGIGRAY72 = (183, 183, 183)
SGIGRAY76 = (193, 193, 193)
SGIGRAY92 = (234, 234, 234)
SGIGRAY96 = (244, 244, 244)
SGILIGHTBLUE = (125, 158, 192)
SGILIGHTGRAY = (170, 170, 170)
SGIOLIVEDRAB = (142, 142, 56)
SGISALMON = (198, 113, 113)
SGISLATEBLUE = (113, 113, 198)
SGITEAL = (56, 142, 142)
SIENNA = (160, 82, 45)
SIENNA1 = (255, 130, 71)
SIENNA2 = (238, 121, 66)
SIENNA3 = (205, 104, 57)
SIENNA4 = (139, 71, 38)
SILVER = (192, 192, 192)
SKYBLUE = (135, 206, 235)
SKYBLUE1 = (135, 206, 255)
SKYBLUE2 = (126, 192, 238)
SKYBLUE3 = (108, 166, 205)
SKYBLUE4 = (74, 112, 139)
SLATEBLUE = (106, 90, 205)
SLATEBLUE1 = (131, 111, 255)
SLATEBLUE2 = (122, 103, 238)
SLATEBLUE3 = (105, 89, 205)
SLATEBLUE4 = (71, 60, 139)
SLATEGRAY = (112, 128, 144)
SLATEGRAY1 = (198, 226, 255)
SLATEGRAY2 = (185, 211, 238)
SLATEGRAY3 = (159, 182, 205)
SLATEGRAY4 = (108, 123, 139)
SNOW1 = (255, 250, 250)
SNOW2 = (238, 233, 233)
SNOW3 = (205, 201, 201)
SNOW4 = (139, 137, 137)
SPRINGGREEN = (0, 255, 127)
SPRINGGREEN1 = (0, 238, 118)
SPRINGGREEN2 = (0, 205, 102)
SPRINGGREEN3 = (0, 139, 69)
STEELBLUE = (70, 130, 180)
STEELBLUE1 = (99, 184, 255)
STEELBLUE2 = (92, 172, 238)
STEELBLUE3 = (79, 148, 205)
STEELBLUE4 = (54, 100, 139)
TAN = (210, 180, 140)
TAN1 = (255, 165, 79)
TAN2 = (238, 154, 73)
TAN3 = (205, 133, 63)
TAN4 = (139, 90, 43)
TEAL = (0, 128, 128)
THISTLE = (216, 191, 216)
THISTLE1 = (255, 225, 255)
THISTLE2 = (238, 210, 238)
THISTLE3 = (205, 181, 205)
THISTLE4 = (139, 123, 139)
TOMATO1 = (255, 99, 71)
TOMATO2 = (238, 92, 66)
TOMATO3 = (205, 79, 57)
TOMATO4 = (139, 54, 38)
TURQUOISE = (64, 224, 208)
TURQUOISE1 = (0, 245, 255)
TURQUOISE2 = (0, 229, 238)
TURQUOISE3 = (0, 197, 205)
TURQUOISE4 = (0, 134, 139)
TURQUOISEBLUE = (0, 199, 140)
VIOLET = (238, 130, 238)
VIOLETRED = (208, 32, 144)
VIOLETRED1 = (255, 62, 150)
VIOLETRED2 = (238, 58, 140)
VIOLETRED3 = (205, 50, 120)
VIOLETRED4 = (139, 34, 82)
WARMGREY = (128, 128, 105)
WHEAT = (245, 222, 179)
WHEAT1 = (255, 231, 186)
WHEAT2 = (238, 216, 174)
WHEAT3 = (205, 186, 150)
WHEAT4 = (139, 126, 102)
WHITE = (255, 255, 255)
WHITESMOKE = (245, 245, 245)
WHITESMOKE = (245, 245, 245)
YELLOW1 = (255, 255, 0)
YELLOW2 = (238, 238, 0)
YELLOW3 = (205, 205, 0)
YELLOW4 = (139, 139, 0)
colors["aliceblue"] = ALICEBLUE
colors["antiquewhite"] = ANTIQUEWHITE
colors["antiquewhite1"] = ANTIQUEWHITE1
colors["antiquewhite2"] = ANTIQUEWHITE2
colors["antiquewhite3"] = ANTIQUEWHITE3
colors["antiquewhite4"] = ANTIQUEWHITE4
colors["aqua"] = AQUA
colors["aquamarine1"] = AQUAMARINE1
colors["aquamarine2"] = AQUAMARINE2
colors["aquamarine3"] = AQUAMARINE3
colors["aquamarine4"] = AQUAMARINE4
colors["azure1"] = AZURE1
colors["azure2"] = AZURE2
colors["azure3"] = AZURE3
colors["azure4"] = AZURE4
colors["banana"] = BANANA
colors["beige"] = BEIGE
colors["bisque1"] = BISQUE1
colors["bisque2"] = BISQUE2
colors["bisque3"] = BISQUE3
colors["bisque4"] = BISQUE4
colors["black"] = BLACK
colors["blanchedalmond"] = BLANCHEDALMOND
colors["blue"] = BLUE
colors["blue2"] = BLUE2
colors["blue3"] = BLUE3
colors["blue4"] = BLUE4
colors["blueviolet"] = BLUEVIOLET
colors["brick"] = BRICK
colors["brown"] = BROWN
colors["brown1"] = BROWN1
colors["brown2"] = BROWN2
colors["brown3"] = BROWN3
colors["brown4"] = BROWN4
colors["burlywood"] = BURLYWOOD
colors["burlywood1"] = BURLYWOOD1
colors["burlywood2"] = BURLYWOOD2
colors["burlywood3"] = BURLYWOOD3
colors["burlywood4"] = BURLYWOOD4
colors["burntsienna"] = BURNTSIENNA
colors["burntumber"] = BURNTUMBER
colors["cadetblue"] = CADETBLUE
colors["cadetblue1"] = CADETBLUE1
colors["cadetblue2"] = CADETBLUE2
colors["cadetblue3"] = CADETBLUE3
colors["cadetblue4"] = CADETBLUE4
colors["cadmiumorange"] = CADMIUMORANGE
colors["cadmiumyellow"] = CADMIUMYELLOW
colors["carrot"] = CARROT
colors["chartreuse1"] = CHARTREUSE1
colors["chartreuse2"] = CHARTREUSE2
colors["chartreuse3"] = CHARTREUSE3
colors["chartreuse4"] = CHARTREUSE4
colors["chocolate"] = CHOCOLATE
colors["chocolate1"] = CHOCOLATE1
colors["chocolate2"] = CHOCOLATE2
colors["chocolate3"] = CHOCOLATE3
colors["chocolate4"] = CHOCOLATE4
colors["cobalt"] = COBALT
colors["cobaltgreen"] = COBALTGREEN
colors["coldgrey"] = COLDGREY
colors["coral"] = CORAL
colors["coral1"] = CORAL1
colors["coral2"] = CORAL2
colors["coral3"] = CORAL3
colors["coral4"] = CORAL4
colors["cornflowerblue"] = CORNFLOWERBLUE
colors["cornsilk1"] = CORNSILK1
colors["cornsilk2"] = CORNSILK2
colors["cornsilk3"] = CORNSILK3
colors["cornsilk4"] = CORNSILK4
colors["crimson"] = CRIMSON
colors["cyan2"] = CYAN2
colors["cyan3"] = CYAN3
colors["cyan4"] = CYAN4
colors["darkgoldenrod"] = DARKGOLDENROD
colors["darkgoldenrod1"] = DARKGOLDENROD1
colors["darkgoldenrod2"] = DARKGOLDENROD2
colors["darkgoldenrod3"] = DARKGOLDENROD3
colors["darkgoldenrod4"] = DARKGOLDENROD4
colors["darkgray"] = DARKGRAY
colors["darkgreen"] = DARKGREEN
colors["darkkhaki"] = DARKKHAKI
colors["darkolivegreen"] = DARKOLIVEGREEN
colors["darkolivegreen1"] = DARKOLIVEGREEN1
colors["darkolivegreen2"] = DARKOLIVEGREEN2
colors["darkolivegreen3"] = DARKOLIVEGREEN3
colors["darkolivegreen4"] = DARKOLIVEGREEN4
colors["darkorange"] = DARKORANGE
colors["darkorange1"] = DARKORANGE1
colors["darkorange2"] = DARKORANGE2
colors["darkorange3"] = DARKORANGE3
colors["darkorange4"] = DARKORANGE4
colors["darkorchid"] = DARKORCHID
colors["darkorchid1"] = DARKORCHID1
colors["darkorchid2"] = DARKORCHID2
colors["darkorchid3"] = DARKORCHID3
colors["darkorchid4"] = DARKORCHID4
colors["darksalmon"] = DARKSALMON
colors["darkseagreen"] = DARKSEAGREEN
colors["darkseagreen1"] = DARKSEAGREEN1
colors["darkseagreen2"] = DARKSEAGREEN2
colors["darkseagreen3"] = DARKSEAGREEN3
colors["darkseagreen4"] = DARKSEAGREEN4
colors["darkslateblue"] = DARKSLATEBLUE
colors["darkslategray"] = DARKSLATEGRAY
colors["darkslategray1"] = DARKSLATEGRAY1
colors["darkslategray2"] = DARKSLATEGRAY2
colors["darkslategray3"] = DARKSLATEGRAY3
colors["darkslategray4"] = DARKSLATEGRAY4
colors["darkturquoise"] = DARKTURQUOISE
colors["darkviolet"] = DARKVIOLET
colors["deeppink1"] = DEEPPINK1
colors["deeppink2"] = DEEPPINK2
colors["deeppink3"] = DEEPPINK3
colors["deeppink4"] = DEEPPINK4
colors["deepskyblue1"] = DEEPSKYBLUE1
colors["deepskyblue2"] = DEEPSKYBLUE2
colors["deepskyblue3"] = DEEPSKYBLUE3
colors["deepskyblue4"] = DEEPSKYBLUE4
colors["dimgray"] = DIMGRAY
colors["dimgray"] = DIMGRAY
colors["dodgerblue1"] = DODGERBLUE1
colors["dodgerblue2"] = DODGERBLUE2
colors["dodgerblue3"] = DODGERBLUE3
colors["dodgerblue4"] = DODGERBLUE4
colors["eggshell"] = EGGSHELL
colors["emeraldgreen"] = EMERALDGREEN
colors["firebrick"] = FIREBRICK
colors["firebrick1"] = FIREBRICK1
colors["firebrick2"] = FIREBRICK2
colors["firebrick3"] = FIREBRICK3
colors["firebrick4"] = FIREBRICK4
colors["flesh"] = FLESH
colors["floralwhite"] = FLORALWHITE
colors["forestgreen"] = FORESTGREEN
colors["gainsboro"] = GAINSBORO
colors["ghostwhite"] = GHOSTWHITE
colors["gold1"] = GOLD1
colors["gold2"] = GOLD2
colors["gold3"] = GOLD3
colors["gold4"] = GOLD4
colors["goldenrod"] = GOLDENROD
colors["goldenrod1"] = GOLDENROD1
colors["goldenrod2"] = GOLDENROD2
colors["goldenrod3"] = GOLDENROD3
colors["goldenrod4"] = GOLDENROD4
colors["gray"] = GRAY
colors["gray1"] = GRAY1
colors["gray10"] = GRAY10
colors["gray11"] = GRAY11
colors["gray12"] = GRAY12
colors["gray13"] = GRAY13
colors["gray14"] = GRAY14
colors["gray15"] = GRAY15
colors["gray16"] = GRAY16
colors["gray17"] = GRAY17
colors["gray18"] = GRAY18
colors["gray19"] = GRAY19
colors["gray2"] = GRAY2
colors["gray20"] = GRAY20
colors["gray21"] = GRAY21
colors["gray22"] = GRAY22
colors["gray23"] = GRAY23
colors["gray24"] = GRAY24
colors["gray25"] = GRAY25
colors["gray26"] = GRAY26
colors["gray27"] = GRAY27
colors["gray28"] = GRAY28
colors["gray29"] = GRAY29
colors["gray3"] = GRAY3
colors["gray30"] = GRAY30
colors["gray31"] = GRAY31
colors["gray32"] = GRAY32
colors["gray33"] = GRAY33
colors["gray34"] = GRAY34
colors["gray35"] = GRAY35
colors["gray36"] = GRAY36
colors["gray37"] = GRAY37
colors["gray38"] = GRAY38
colors["gray39"] = GRAY39
colors["gray4"] = GRAY4
colors["gray40"] = GRAY40
colors["gray42"] = GRAY42
colors["gray43"] = GRAY43
colors["gray44"] = GRAY44
colors["gray45"] = GRAY45
colors["gray46"] = GRAY46
colors["gray47"] = GRAY47
colors["gray48"] = GRAY48
colors["gray49"] = GRAY49
colors["gray5"] = GRAY5
colors["gray50"] = GRAY50
colors["gray51"] = GRAY51
colors["gray52"] = GRAY52
colors["gray53"] = GRAY53
colors["gray54"] = GRAY54
colors["gray55"] = GRAY55
colors["gray56"] = GRAY56
colors["gray57"] = GRAY57
colors["gray58"] = GRAY58
colors["gray59"] = GRAY59
colors["gray6"] = GRAY6
colors["gray60"] = GRAY60
colors["gray61"] = GRAY61
colors["gray62"] = GRAY62
colors["gray63"] = GRAY63
colors["gray64"] = GRAY64
colors["gray65"] = GRAY65
colors["gray66"] = GRAY66
colors["gray67"] = GRAY67
colors["gray68"] = GRAY68
colors["gray69"] = GRAY69
colors["gray7"] = GRAY7
colors["gray70"] = GRAY70
colors["gray71"] = GRAY71
colors["gray72"] = GRAY72
colors["gray73"] = GRAY73
colors["gray74"] = GRAY74
colors["gray75"] = GRAY75
colors["gray76"] = GRAY76
colors["gray77"] = GRAY77
colors["gray78"] = GRAY78
colors["gray79"] = GRAY79
colors["gray8"] = GRAY8
colors["gray80"] = GRAY80
colors["gray81"] = GRAY81
colors["gray82"] = GRAY82
colors["gray83"] = GRAY83
colors["gray84"] = GRAY84
colors["gray85"] = GRAY85
colors["gray86"] = GRAY86
colors["gray87"] = GRAY87
colors["gray88"] = GRAY88
colors["gray89"] = GRAY89
colors["gray9"] = GRAY9
colors["gray90"] = GRAY90
colors["gray91"] = GRAY91
colors["gray92"] = GRAY92
colors["gray93"] = GRAY93
colors["gray94"] = GRAY94
colors["gray95"] = GRAY95
colors["gray97"] = GRAY97
colors["gray98"] = GRAY98
colors["gray99"] = GRAY99
colors["green"] = GREEN
colors["green1"] = GREEN1
colors["green2"] = GREEN2
colors["green3"] = GREEN3
colors["green4"] = GREEN4
colors["greenyellow"] = GREENYELLOW
colors["honeydew1"] = HONEYDEW1
colors["honeydew2"] = HONEYDEW2
colors["honeydew3"] = HONEYDEW3
colors["honeydew4"] = HONEYDEW4
colors["hotpink"] = HOTPINK
colors["hotpink1"] = HOTPINK1
colors["hotpink2"] = HOTPINK2
colors["hotpink3"] = HOTPINK3
colors["hotpink4"] = HOTPINK4
colors["indianred"] = INDIANRED
colors["indianred"] = INDIANRED
colors["indianred1"] = INDIANRED1
colors["indianred2"] = INDIANRED2
colors["indianred3"] = INDIANRED3
colors["indianred4"] = INDIANRED4
colors["indigo"] = INDIGO
colors["ivory1"] = IVORY1
colors["ivory2"] = IVORY2
colors["ivory3"] = IVORY3
colors["ivory4"] = IVORY4
colors["ivoryblack"] = IVORYBLACK
colors["khaki"] = KHAKI
colors["khaki1"] = KHAKI1
colors["khaki2"] = KHAKI2
colors["khaki3"] = KHAKI3
colors["khaki4"] = KHAKI4
colors["lavender"] = LAVENDER
colors["lavenderblush1"] = LAVENDERBLUSH1
colors["lavenderblush2"] = LAVENDERBLUSH2
colors["lavenderblush3"] = LAVENDERBLUSH3
colors["lavenderblush4"] = LAVENDERBLUSH4
colors["lawngreen"] = LAWNGREEN
colors["lemonchiffon1"] = LEMONCHIFFON1
colors["lemonchiffon2"] = LEMONCHIFFON2
colors["lemonchiffon3"] = LEMONCHIFFON3
colors["lemonchiffon4"] = LEMONCHIFFON4
colors["lightblue"] = LIGHTBLUE
colors["lightblue1"] = LIGHTBLUE1
colors["lightblue2"] = LIGHTBLUE2
colors["lightblue3"] = LIGHTBLUE3
colors["lightblue4"] = LIGHTBLUE4
colors["lightcoral"] = LIGHTCORAL
colors["lightcyan1"] = LIGHTCYAN1
colors["lightcyan2"] = LIGHTCYAN2
colors["lightcyan3"] = LIGHTCYAN3
colors["lightcyan4"] = LIGHTCYAN4
colors["lightgoldenrod1"] = LIGHTGOLDENROD1
colors["lightgoldenrod2"] = LIGHTGOLDENROD2
colors["lightgoldenrod3"] = LIGHTGOLDENROD3
colors["lightgoldenrod4"] = LIGHTGOLDENROD4
colors["lightgoldenrodyellow"] = LIGHTGOLDENRODYELLOW
colors["lightgrey"] = LIGHTGREY
colors["lightpink"] = LIGHTPINK
colors["lightpink1"] = LIGHTPINK1
colors["lightpink2"] = LIGHTPINK2
colors["lightpink3"] = LIGHTPINK3
colors["lightpink4"] = LIGHTPINK4
colors["lightsalmon1"] = LIGHTSALMON1
colors["lightsalmon2"] = LIGHTSALMON2
colors["lightsalmon3"] = LIGHTSALMON3
colors["lightsalmon4"] = LIGHTSALMON4
colors["lightseagreen"] = LIGHTSEAGREEN
colors["lightskyblue"] = LIGHTSKYBLUE
colors["lightskyblue1"] = LIGHTSKYBLUE1
colors["lightskyblue2"] = LIGHTSKYBLUE2
colors["lightskyblue3"] = LIGHTSKYBLUE3
colors["lightskyblue4"] = LIGHTSKYBLUE4
colors["lightslateblue"] = LIGHTSLATEBLUE
colors["lightslategray"] = LIGHTSLATEGRAY
colors["lightsteelblue"] = LIGHTSTEELBLUE
colors["lightsteelblue1"] = LIGHTSTEELBLUE1
colors["lightsteelblue2"] = LIGHTSTEELBLUE2
colors["lightsteelblue3"] = LIGHTSTEELBLUE3
colors["lightsteelblue4"] = LIGHTSTEELBLUE4
colors["lightyellow1"] = LIGHTYELLOW1
colors["lightyellow2"] = LIGHTYELLOW2
colors["lightyellow3"] = LIGHTYELLOW3
colors["lightyellow4"] = LIGHTYELLOW4
colors["limegreen"] = LIMEGREEN
colors["linen"] = LINEN
colors["magenta"] = MAGENTA
colors["magenta2"] = MAGENTA2
colors["magenta3"] = MAGENTA3
colors["magenta4"] = MAGENTA4
colors["manganeseblue"] = MANGANESEBLUE
colors["maroon"] = MAROON
colors["maroon1"] = MAROON1
colors["maroon2"] = MAROON2
colors["maroon3"] = MAROON3
colors["maroon4"] = MAROON4
colors["mediumorchid"] = MEDIUMORCHID
colors["mediumorchid1"] = MEDIUMORCHID1
colors["mediumorchid2"] = MEDIUMORCHID2
colors["mediumorchid3"] = MEDIUMORCHID3
colors["mediumorchid4"] = MEDIUMORCHID4
colors["mediumpurple"] = MEDIUMPURPLE
colors["mediumpurple1"] = MEDIUMPURPLE1
colors["mediumpurple2"] = MEDIUMPURPLE2
colors["mediumpurple3"] = MEDIUMPURPLE3
colors["mediumpurple4"] = MEDIUMPURPLE4
colors["mediumseagreen"] = MEDIUMSEAGREEN
colors["mediumslateblue"] = MEDIUMSLATEBLUE
colors["mediumspringgreen"] = MEDIUMSPRINGGREEN
colors["mediumturquoise"] = MEDIUMTURQUOISE
colors["mediumvioletred"] = MEDIUMVIOLETRED
colors["melon"] = MELON
colors["midnightblue"] = MIDNIGHTBLUE
colors["mint"] = MINT
colors["mintcream"] = MINTCREAM
colors["mistyrose1"] = MISTYROSE1
colors["mistyrose2"] = MISTYROSE2
colors["mistyrose3"] = MISTYROSE3
colors["mistyrose4"] = MISTYROSE4
colors["moccasin"] = MOCCASIN
colors["navajowhite1"] = NAVAJOWHITE1
colors["navajowhite2"] = NAVAJOWHITE2
colors["navajowhite3"] = NAVAJOWHITE3
colors["navajowhite4"] = NAVAJOWHITE4
colors["navy"] = NAVY
colors["oldlace"] = OLDLACE
colors["olive"] = OLIVE
colors["olivedrab"] = OLIVEDRAB
colors["olivedrab1"] = OLIVEDRAB1
colors["olivedrab2"] = OLIVEDRAB2
colors["olivedrab3"] = OLIVEDRAB3
colors["olivedrab4"] = OLIVEDRAB4
colors["orange"] = ORANGE
colors["orange1"] = ORANGE1
colors["orange2"] = ORANGE2
colors["orange3"] = ORANGE3
colors["orange4"] = ORANGE4
colors["orangered1"] = ORANGERED1
colors["orangered2"] = ORANGERED2
colors["orangered3"] = ORANGERED3
colors["orangered4"] = ORANGERED4
colors["orchid"] = ORCHID
colors["orchid1"] = ORCHID1
colors["orchid2"] = ORCHID2
colors["orchid3"] = ORCHID3
colors["orchid4"] = ORCHID4
colors["palegoldenrod"] = PALEGOLDENROD
colors["palegreen"] = PALEGREEN
colors["palegreen1"] = PALEGREEN1
colors["palegreen2"] = PALEGREEN2
colors["palegreen3"] = PALEGREEN3
colors["palegreen4"] = PALEGREEN4
colors["paleturquoise1"] = PALETURQUOISE1
colors["paleturquoise2"] = PALETURQUOISE2
colors["paleturquoise3"] = PALETURQUOISE3
colors["paleturquoise4"] = PALETURQUOISE4
colors["palevioletred"] = PALEVIOLETRED
colors["palevioletred1"] = PALEVIOLETRED1
colors["palevioletred2"] = PALEVIOLETRED2
colors["palevioletred3"] = PALEVIOLETRED3
colors["palevioletred4"] = PALEVIOLETRED4
colors["papayawhip"] = PAPAYAWHIP
colors["peachpuff1"] = PEACHPUFF1
colors["peachpuff2"] = PEACHPUFF2
colors["peachpuff3"] = PEACHPUFF3
colors["peachpuff4"] = PEACHPUFF4
colors["peacock"] = PEACOCK
colors["pink"] = PINK
colors["pink1"] = PINK1
colors["pink2"] = PINK2
colors["pink3"] = PINK3
colors["pink4"] = PINK4
colors["plum"] = PLUM
colors["plum1"] = PLUM1
colors["plum2"] = PLUM2
colors["plum3"] = PLUM3
colors["plum4"] = PLUM4
colors["powderblue"] = POWDERBLUE
colors["purple"] = PURPLE
colors["purple1"] = PURPLE1
colors["purple2"] = PURPLE2
colors["purple3"] = PURPLE3
colors["purple4"] = PURPLE4
colors["raspberry"] = RASPBERRY
colors["rawsienna"] = RAWSIENNA
colors["red1"] = RED1
colors["red2"] = RED2
colors["red3"] = RED3
colors["red4"] = RED4
colors["rosybrown"] = ROSYBROWN
colors["rosybrown1"] = ROSYBROWN1
colors["rosybrown2"] = ROSYBROWN2
colors["rosybrown3"] = ROSYBROWN3
colors["rosybrown4"] = ROSYBROWN4
colors["royalblue"] = ROYALBLUE
colors["royalblue1"] = ROYALBLUE1
colors["royalblue2"] = ROYALBLUE2
colors["royalblue3"] = ROYALBLUE3
colors["royalblue4"] = ROYALBLUE4
colors["salmon"] = SALMON
colors["salmon1"] = SALMON1
colors["salmon2"] = SALMON2
colors["salmon3"] = SALMON3
colors["salmon4"] = SALMON4
colors["sandybrown"] = SANDYBROWN
colors["sapgreen"] = SAPGREEN
colors["seagreen1"] = SEAGREEN1
colors["seagreen2"] = SEAGREEN2
colors["seagreen3"] = SEAGREEN3
colors["seagreen4"] = SEAGREEN4
colors["seashell1"] = SEASHELL1
colors["seashell2"] = SEASHELL2
colors["seashell3"] = SEASHELL3
colors["seashell4"] = SEASHELL4
colors["sepia"] = SEPIA
colors["sgibeet"] = SGIBEET
colors["sgibrightgray"] = SGIBRIGHTGRAY
colors["sgichartreuse"] = SGICHARTREUSE
colors["sgidarkgray"] = SGIDARKGRAY
colors["sgigray12"] = SGIGRAY12
colors["sgigray16"] = SGIGRAY16
colors["sgigray32"] = SGIGRAY32
colors["sgigray36"] = SGIGRAY36
colors["sgigray52"] = SGIGRAY52
colors["sgigray56"] = SGIGRAY56
colors["sgigray72"] = SGIGRAY72
colors["sgigray76"] = SGIGRAY76
colors["sgigray92"] = SGIGRAY92
colors["sgigray96"] = SGIGRAY96
colors["sgilightblue"] = SGILIGHTBLUE
colors["sgilightgray"] = SGILIGHTGRAY
colors["sgiolivedrab"] = SGIOLIVEDRAB
colors["sgisalmon"] = SGISALMON
colors["sgislateblue"] = SGISLATEBLUE
colors["sgiteal"] = SGITEAL
colors["sienna"] = SIENNA
colors["sienna1"] = SIENNA1
colors["sienna2"] = SIENNA2
colors["sienna3"] = SIENNA3
colors["sienna4"] = SIENNA4
colors["silver"] = SILVER
colors["skyblue"] = SKYBLUE
colors["skyblue1"] = SKYBLUE1
colors["skyblue2"] = SKYBLUE2
colors["skyblue3"] = SKYBLUE3
colors["skyblue4"] = SKYBLUE4
colors["slateblue"] = SLATEBLUE
colors["slateblue1"] = SLATEBLUE1
colors["slateblue2"] = SLATEBLUE2
colors["slateblue3"] = SLATEBLUE3
colors["slateblue4"] = SLATEBLUE4
colors["slategray"] = SLATEGRAY
colors["slategray1"] = SLATEGRAY1
colors["slategray2"] = SLATEGRAY2
colors["slategray3"] = SLATEGRAY3
colors["slategray4"] = SLATEGRAY4
colors["snow1"] = SNOW1
colors["snow2"] = SNOW2
colors["snow3"] = SNOW3
colors["snow4"] = SNOW4
colors["springgreen"] = SPRINGGREEN
colors["springgreen1"] = SPRINGGREEN1
colors["springgreen2"] = SPRINGGREEN2
colors["springgreen3"] = SPRINGGREEN3
colors["steelblue"] = STEELBLUE
colors["steelblue1"] = STEELBLUE1
colors["steelblue2"] = STEELBLUE2
colors["steelblue3"] = STEELBLUE3
colors["steelblue4"] = STEELBLUE4
colors["tan"] = TAN
colors["tan1"] = TAN1
colors["tan2"] = TAN2
colors["tan3"] = TAN3
colors["tan4"] = TAN4
colors["teal"] = TEAL
colors["thistle"] = THISTLE
colors["thistle1"] = THISTLE1
colors["thistle2"] = THISTLE2
colors["thistle3"] = THISTLE3
colors["thistle4"] = THISTLE4
colors["tomato1"] = TOMATO1
colors["tomato2"] = TOMATO2
colors["tomato3"] = TOMATO3
colors["tomato4"] = TOMATO4
colors["turquoise"] = TURQUOISE
colors["turquoise1"] = TURQUOISE1
colors["turquoise2"] = TURQUOISE2
colors["turquoise3"] = TURQUOISE3
colors["turquoise4"] = TURQUOISE4
colors["turquoiseblue"] = TURQUOISEBLUE
colors["violet"] = VIOLET
colors["violetred"] = VIOLETRED
colors["violetred1"] = VIOLETRED1
colors["violetred2"] = VIOLETRED2
colors["violetred3"] = VIOLETRED3
colors["violetred4"] = VIOLETRED4
colors["warmgrey"] = WARMGREY
colors["wheat"] = WHEAT
colors["wheat1"] = WHEAT1
colors["wheat2"] = WHEAT2
colors["wheat3"] = WHEAT3
colors["wheat4"] = WHEAT4
colors["white"] = WHITE
colors["whitesmoke"] = WHITESMOKE
colors["whitesmoke"] = WHITESMOKE
colors["yellow1"] = YELLOW1
colors["yellow2"] = YELLOW2
colors["yellow3"] = YELLOW3
colors["yellow4"] = YELLOW4


class Color:
    def __init__(self, *args, color_type="rgb") -> None:
        if len(args) == 0:  # If no color is passed
            self.r, self.g, self.b = (0, 0, 0)
        elif len(args) == 1:  # If a single arg is pass
            if isinstance(args[0], str):  # If it is a string
                if (
                    args[0].lower().replace(" ", "") in colors
                ):  # If it is a color name, grab color name and apply it
                    self.r, self.g, self.b = colors[args[0].lower().replace(" ", "")]
                else:  # Otherwise assume hex code
                    color_int = int(args[0].strip().replace("#", ""), base=16)
                    if color_type.lower() == "rgb":
                        self.b, self.g, self.r = [
                            color_int & 255,
                            (color_int >> 8) & 255,
                            (color_int >> 16) & 255,
                        ]
            if isinstance(args[0], tuple) or isinstance(
                args[0], list
            ):  # If it is a list or tuple, repass to Color unwrapped
                color = Color(*args[0], color_type=color_type)
                self.r, self.g, self.b = [color.r, color.g, color.b]
        elif len(args) == 3:  # If 3 args
            if color_type.lower() == "rgb":  # Easy if rgb
                self.r, self.g, self.b = args
            elif color_type.lower() == "hsv":  # Convert to rgb from hsv
                self.r, self.g, self.b = colorsys.hsv_to_rgb(
                    args[0] / 360, args[1] / 100, args[2] / 100
                )
                self.r *= 255
                self.g *= 255
                self.b *= 255

        # Clamp values
        self.r = max(min(self.r, 255), 0)
        self.g = max(min(self.g, 255), 0)
        self.b = max(min(self.b, 255), 0)

    def __str__(self):  # Return hex code
        return "#" + "".join(
            [hex(round(i))[2:].rjust(2, "0") for i in [self.r, self.g, self.b]]
        )

    def _to_prop(self):
        return self.__str__()

    @property
    def brightness(self):  # Get how bright color is
        brightness = 0.0
        for i in [self.r, self.g, self.b]:
            if i / 255 > brightness:
                brightness = i / 255
        return brightness

    @property
    def darkness(self):  # Get how dark color is
        darkness = 1.0
        for i in [self.r, self.g, self.b]:
            if i / 255 < darkness:
                darkness = i / 255
        return abs(1 - darkness)

    def to_hsv(self) -> tuple[float, float, float]:  # Get hsv ruple
        result = list(colorsys.rgb_to_hsv(*[self.r, self.g, self.b]))
        result[2] /= 255
        return tuple(result)

    def inverted(self):  # Get inverted color
        return Color(abs(255 - self.r), abs(255 - self.g), abs(255 - self.b))

    def darkend(self, amount=16):  # Get darkend color
        return Color(
            max(self.r - amount, 0), max(self.g - amount, 0), max(self.b - amount, 0)
        )

    def lightend(self, amount=16):  # Get lightend color
        return Color(
            min(self.r + amount, 255),
            min(self.g + amount, 255),
            min(self.b + amount, 255),
        )

    def complementary(self):  # Get complementary color
        result = list(self.to_hsv())
        result[0] = 1 - result[0]
        return Color(
            result[0] * 360, result[1] * 100, result[2] * 100, color_type="hsv"
        )

    def highlight(self):
        result = list(self.to_hsv())
        result[1] *= 2
        result[1] = min(result[1], 1)
        result[2] = min(result[2] + 0.2, 1)
        return Color(
            result[0] * 360, result[1] * 100, result[2] * 100, color_type="hsv"
        )


class Palette:
    main_color: Color = Color()
    darkmode: bool = False
    color_type: str = "rgb"
    hue_shift: int = 48
    variation_extreme: float = 0.47
    saturation_slope: int = -4
    darkmode_threshold: float = 0.5

    def __init__(
        self,
        *args,
        color_type="rgb",
        hue_shift=48,
        variation_extreme=0.47,
        saturation_slope=-4,
        darkmode_threshold=0.5,
    ):
        super().__init__()
        self.hue_shift = hue_shift
        self.variation_extreme = variation_extreme
        self.saturation_slope = saturation_slope
        self.darkmode_threshold = darkmode_threshold
        if isinstance(args[0], Color):
            self.main_color = args[0]
        else:
            self.main_color = Color(*args, color_type=color_type)
        self.darkmode = False

    def _get_darkmode(self, color):
        if color.brightness - color.darkness > self.darkmode_threshold:
            return color.inverted().darkend()
        elif color.darkness - color.brightness > self.darkmode_threshold:
            hsv = list(color.to_hsv())
            hsv[2] += 0.5
            hsv[2] = min(hsv[2], 1)
            return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")
        return color

    def get_shade(self, shade):
        hsv = list(self.main_color.to_hsv())
        hsv[0] = ((self.hue_shift / 180) * (shade - 0.5) + hsv[0]) % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        if self.darkmode:
            hsv = self._get_darkmode(
                Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")
            ).to_hsv()
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def get_inverted_shade(self, shade):
        hsv = list(self.main_color.inverted().to_hsv())
        hsv[0] = (self.hue_shift / 180) * (shade - 0.5) + hsv[0] % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def get_darkend_shade(self, shade, amount=16):
        hsv = list(self.main_color.darkend(amount).to_hsv())
        hsv[0] = (self.hue_shift / 180) * (shade - 0.5) + hsv[0] % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        if self.darkmode:
            hsv = self._get_darkmode(
                Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")
            ).to_hsv()
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def get_lightend_shade(self, shade, amount=16):
        hsv = list(self.main_color.lightend(amount).to_hsv())
        hsv[0] = (self.hue_shift / 180) * (shade - 0.5) + hsv[0] % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        if self.darkmode:
            hsv = self._get_darkmode(
                Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")
            ).to_hsv()
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def get_complementary_shade(self, shade):
        hsv = list(self.main_color.complementary().to_hsv())
        hsv[0] = (self.hue_shift / 180) * (shade - 0.5) + hsv[0] % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        if self.darkmode:
            hsv = self._get_darkmode(
                Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")
            ).to_hsv()
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def get_highlight_shade(self, shade):
        hsv = list(self.main_color.highlight().to_hsv())
        hsv[0] = (self.hue_shift / 180) * (shade - 0.5) + hsv[0] % 1
        hsv[1] = self.saturation_slope * (shade - 0.5) + hsv[1]
        hsv[2] = (
            self.variation_extreme * sqrt(shade)
            + hsv[2]
            - sqrt(0.5)
            + sqrt(0.5) * (1 - self.variation_extreme)
        )
        hsv[0] = max(min(hsv[0], 1), 0)
        hsv[1] = max(min(hsv[1], 1), 0)
        hsv[2] = max(min(hsv[2], 1), 0)
        return Color(hsv[0] * 360, hsv[1] * 100, hsv[2] * 100, color_type="hsv")

    def to_dict(self, **extra_shades: Color):
        result = {}
        for i in self.__dir__():
            if isinstance(getattr(self, i), Color):
                result[i] = str(getattr(self, i))
        for key, value in extra_shades.items():
            if isinstance(value, float) or isinstance(value, int):
                result[key] = str(self.get_shade(value))
            elif isinstance(value, str):
                if value.__contains__("(") and value.__contains__(")"):
                    func, args = value.split("(")
                    args = eval("[" + args.replace(")", "]"))
                    result[key] = str(getattr(self, f"get_{func}_shade")(*args))
            elif isinstance(value, Color):
                result[key] = str(value)
        return result

    @property
    def bg(self):
        return self.get_shade(0.95)

    @property
    def bg1(self):
        return self.bg

    @property
    def bg2(self):
        return self.get_shade(0.8)

    @property
    def bg3(self):
        return self.get_shade(0.65)

    @property
    def highlight(self):
        return self.get_highlight_shade(0.1)

    @property
    def highlight1(self):
        return self.highlight

    @property
    def highlight2(self):
        return self.get_highlight_shade(0.3)

    @property
    def highlight3(self):
        return self.get_highlight_shade(0.4)

    @property
    def dark(self):
        return self.get_shade(0)

    @property
    def light(self):
        return self.get_shade(0.65)

    @property
    def text(self):
        return self.get_darkend_shade(0.4)
    
    @property
    def complementary(self):
        return self.get_complementary_shade(0.5)
