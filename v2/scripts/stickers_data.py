"""The 20 stickers: pose, expression, props, 2D decorations and captions (no Blender imports).
Keep this file UTF-8: it holds the Khmer captions."""


def down(s):
    return dict(wrist=(s * .635, -.07, .66), fingers=(-s * .38, -.1, -1), palm=(-s, -.25, .25), curl="relax",
                arrive=(-s * .3, 0, -1), out=(s, -.1, .35))


def wave(s, h=1.0, tilt=.14):
    return dict(wrist=(s * .72, -.06, h), fingers=(s * tilt, 0, 1), palm=(0, -1, 0), curl="open",
                arrive=(s * .25, 0, 1), out=(s, -.1, -.35 if h < 1.1 else .15))


def up(s, h=1.34):
    return dict(wrist=(s * .76, -.05, h), fingers=(s * .35, 0, 1), palm=(0, -1, 0), curl="open",
                arrive=(s * .5, 0, 1), out=(s, 0, .3), k=.22)


def thumbs(s, z=1.0, x=.78):
    return dict(wrist=(s * x, -.24, z), fingers=(-s * .12, -1, .05), palm=(-s, 0, 0), curl="thumbsup",
                arrive=(s * .25, -1, .1), out=(s, -.2, -.25))


def ok(s):
    return dict(wrist=(s * .74, -.14, 1.0), fingers=(s * .10, 0, 1), palm=(0, -1, 0), curl="ok",
                arrive=(s * .25, 0, 1), out=(s, -.1, -.3))


def stop(s):
    return dict(wrist=(s * .66, -.50, .98), fingers=(s * .1, 0, 1), palm=(0, -1, 0), curl="flat",
                arrive=(0, -1, .3), out=(s, -.7, 0), k=.30)


def pray(s, z=.82):
    return dict(wrist=(s * .078, -.67, z), fingers=(0, -.12, 1), palm=(-s, 0, 0), curl="flat",
                arrive=(-s * .9, -.25, .4), out=(s, -.9, -.15), k=.44)


def carry(s, x=.235, z=.70, y=-.56):
    return dict(wrist=(s * x, y, z), fingers=(0, -1, .12), palm=(-s, 0, 0), curl="flat",
                arrive=(-s * .25, -1, 0), out=(s, -.8, -.25), k=.40)


def shrug(s):
    return dict(wrist=(s * .82, -.14, .93), fingers=(s, -.25, .12), palm=(0, -.25, 1), curl="flat",
                arrive=(s, 0, .25), out=(s, 0, -.45))


def hold_side(s, x=.74, z=.86, y=-.2):
    """Hand raised at the side, palm to camera, gripping something."""
    return dict(wrist=(s * x, y, z), fingers=(s * .1, 0, 1), palm=(0, -1, 0), curl="grip",
                arrive=(s * .3, 0, 1), out=(s, -.2, -.35))


def typing(s):
    return dict(wrist=(s * .16, -.74, .80), fingers=(-s * .15, -1, -.25), palm=(0, 0, -1), curl="relax",
                arrive=(-s * .3, -1, -.1), out=(s, -.8, -.1), k=.40)


STAND = dict(legL=dict(foot=(.245, -.03), yaw=24), legR=dict(foot=(-.245, 0.0), yaw=24))


def P(body=None, L=None, R=None, legL=None, legR=None):
    return dict(body=body or {}, armL=L or down(1), armR=R or down(-1),
                legL=legL or STAND["legL"], legR=legR or STAND["legR"])


JUMP = dict(legL=dict(foot=(.27, -.02, .30), yaw=30, pitch=-22), legR=dict(foot=(-.27, .0, .27), yaw=30, pitch=-22))

STICKERS = [
    dict(slug="01_noted", expr="Grateful", text=["NOTED", "WITH THANKS"], pos="top",
         pose=P(L=hold_side(1, x=.70, z=.80, y=-.30), R=hold_side(-1, x=.66, z=.98, y=-.34)),
         props=[("clipboard", (.74, -.42, 1.02), (-8, 0, -10), 1.0), ("pen", (-.66, -.44, 1.13), (0, 28, 0), 1.0)],
         deco=["sparkle:930,470,64", "sparkle:80,640,44"]),
    dict(slug="02_received", expr={"smile_big": .8, "brow_up_L": .6, "brow_up_R": .6}, text=["RECEIVED!"], pos="top",
         pose=P(L=carry(1), R=carry(-1)),
         props=[("parcel", (0, -.70, .70), (0, 0, 0), 1.0)], deco=["sparkle:900,420,64", "sparkle:110,440,52"]),
    dict(slug="03_thank_you", expr="Grateful", text=["អរគុណ", "THANK YOU!"], pos="top",
         pose=P(body=dict(rot=(7, 0, 0)), L=pray(1), R=pray(-1)), deco=["heart:130,560,84", "heart:880,500,66", "heart:930,660,46"]),
    dict(slug="04_hello", expr={"smile_big": .9, "brow_up_L": .8, "brow_up_R": .8}, text=["HELLO!"], pos="top",
         pose=P(body=dict(rot=(0, 5, 0)), R=wave(-1, 1.16, .32)), deco=["waves:105,360,-1"]),
    dict(slug="05_okay", expr="Wink", text=["OKAY!"], pos="top",
         pose=P(R=ok(-1)), deco=["sparkle:900,440,70", "sparkle:950,600,40"]),
    dict(slug="06_good_morning", expr={"smile_big": .6, "brow_up_L": .5, "brow_up_R": .5}, text=["GOOD", "MORNING!"], pos="top",
         pose=P(L=hold_side(1, x=.72, z=.74, y=-.3), R=wave(-1, 1.02)),
         props=[("cup", (.74, -.44, 0.78), (0, 0, 0), 1.25)], deco=["sun:880,470,150"]),
    dict(slug="07_info_inquiry", expr="Thinking", text=["INFORMATION", "INQUIRY"], pos="bottom",
         pose=P(R=hold_side(-1, x=.70, z=.92, y=-.34), L=dict(wrist=(.60, -.16, .74), fingers=(-1, -.3, -.3), palm=(-.2, .2, -1),
                curl="fist", arrive=(-.6, -.2, -1), out=(1, -.1, .2))),
         props=[("magnifier", (-.66, -.50, 1.36), (0, 14, 0), 1.0)], deco=["question:900,170,170", "question:800,90,96"]),
    dict(slug="08_in_meeting", expr="Determined", text=["IN MEETING"], pos="top",
         pose=P(L=typing(1), R=typing(-1)), cam=dict(elev=10),
         props=[("desk", (0, -.92, .70), (0, 0, 0), 0.82), ("laptop", (0, -.86, .75), (0, 0, 0), 1.0)], deco=[]),
    dict(slug="09_yes", expr="Big laugh", text=["ចាស!"], pos="top", yellow=True,
         pose=P(R=thumbs(-1, 1.04)), deco=["sparkle:900,440,72", "sparkle:110,700,44"]),
    dict(slug="10_paid", expr="Excited", text=["PAID!"], pos="top", yellow=True,
         pose=P(L=hold_side(1, x=.70, z=.84, y=-.30), R=thumbs(-1, 1.0)),
         props=[("clipboard_check", (.76, -.42, 1.06), (-8, 0, -10), 1.05)], deco=["sparkle:90,400,60", "coin:930,300,84"]),
    dict(slug="11_please_wait", expr="Calm", text=["PLEASE WAIT!"], pos="top",
         pose=P(R=stop(-1), L=down(1)), deco=["clock:880,400,170"]),
    dict(slug="12_good_afternoon", expr="Happy", text=["GOOD", "AFTERNOON!"], pos="top", yellow=True,
         pose=P(L=wave(1, 1.06, .25)), deco=["sun:150,500,150"]),
    dict(slug="13_sorry", expr={"lids_sad": .6, "look_down": .7, "brow_sad": 1.1, "frown": .8, "fx_sweat": 1}, text=["សុំទោស", "SORRY"], pos="top",
         pose=P(body=dict(rot=(13, 0, 0)), L=pray(1, .80), R=pray(-1, .80)), deco=[]),
    dict(slug="14_on_the_way", expr="Determined", text=["កំពុងដឹកជញ្ជូន", "ON THE WAY!"], pos="top",
         pose=P(body=dict(rot=(5, 0, 0), loc=(0, 0, .05)), L=carry(1), R=carry(-1),
                legL=dict(foot=(.21, -.36, .30), yaw=4, pitch=-28), legR=dict(foot=(-.21, .34, .34), yaw=4, pitch=48)),
         cam=dict(azim=-24), props=[("parcel", (0, -.70, .70), (0, 0, 0), 1.0)], deco=["speed:900,640,150"]),
    dict(slug="15_order_confirmed", expr={"happy_L": 1, "happy_R": 1, "smile_big": .7, "brow_up_L": .5, "brow_up_R": .5},
         text=["បានបញ្ជាក់ការកុម្ម៉ង់", "ORDER CONFIRMED"], pos="top",
         pose=P(L=hold_side(1, x=.70, z=.84, y=-.30), R=ok(-1)),
         props=[("clipboard_check", (.76, -.42, 1.06), (-8, 0, -10), 1.05)], deco=["sparkle:90,470,54"]),
    dict(slug="16_out_of_stock", expr="Worried", text=["អស់ស្តុក", "OUT OF STOCK"], pos="top",
         pose=P(L=shrug(1), R=shrug(-1)), deco=["emptybox:880,880,180"]),
    dict(slug="17_great_job", expr="Big laugh", text=["ល្អណាស់", "GREAT JOB!"], pos="top", yellow=True,
         pose=P(L=thumbs(1, 1.02), R=thumbs(-1, 1.02)), deco=["sparkle:110,440,60", "sparkle:910,440,60"]),
    dict(slug="18_see_you_tomorrow", expr="Wink", text=["ជួបគ្នាថ្ងៃស្អែក", "SEE YOU TOMORROW"], pos="top",
         pose=P(body=dict(rot=(0, -5, 0)), L=wave(1, 1.16, .32)), deco=["moon:130,500,130"]),
    dict(slug="19_congratulations", expr="Excited", text=["សូមអបអរសាទរ", "CONGRATULATIONS!"], pos="bottom", yellow=True,
         pose=P(body=dict(loc=(0, 0, .16)), L=up(1), R=up(-1), legL=JUMP["legL"], legR=JUMP["legR"]), deco=["confetti:512,330,1000"]),
    dict(slug="20_happy_new_year", expr="Love", text=["សួស្តីឆ្នាំថ្មី", "HAPPY NEW YEAR"], pos="top", yellow=True,
         pose=P(L=wave(1, 1.04), R=hold_side(-1, x=.68, z=.84, y=-.32)),
         props=[("envelope", (-.70, -.46, 1.04), (-6, 0, 8), 1.15)], deco=["firework:110,470,130", "firework:920,430,110"]),
]
