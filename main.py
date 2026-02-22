import swisseph as swe
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import nest_asyncio
import uvicorn
# -----------------------------
# FASTAPI INIT
# -----------------------------
app = FastAPI(title="Vedic Astrology API")

# -----------------------------
# INPUT MODEL
# -----------------------------
class BirthInput(BaseModel):
#     date: str   # DD-MM-YYYY
#     time: str   # HH:MM (24hr)
#     city: str
    DOB:str
    TIME:str
    City:str
        
    #date=DOB
        

# -----------------------------
# CONSTANTS
# -----------------------------
RASHI_NAMES = {
    1:"Aries",2:"Taurus",3:"Gemini",4:"Cancer",
    5:"Leo",6:"Virgo",7:"Libra",8:"Scorpio",
    9:"Sagittarius",10:"Capricorn",11:"Aquarius",12:"Pisces"
}

PLANETS = {
    "Sun":swe.SUN,
    "Moon":swe.MOON,
    "Mars":swe.MARS,
    "Mercury":swe.MERCURY,
    "Jupiter":swe.JUPITER,
    "Venus":swe.VENUS,
    "Saturn":swe.SATURN
}

OWN_SIGNS = {
    "Sun": ["Leo"],
    "Moon": ["Cancer"],
    "Mars": ["Aries", "Scorpio"],
    "Mercury": ["Gemini", "Virgo"],
    "Jupiter": ["Sagittarius", "Pisces"],
    "Venus": ["Taurus", "Libra"],
    "Saturn": ["Capricorn", "Aquarius"],
}

EXALTATION_SIGNS = {
    "Sun": "Aries","Moon": "Taurus","Mars": "Capricorn",
    "Mercury": "Virgo","Jupiter": "Cancer",
    "Venus": "Pisces","Saturn": "Libra"
}

DEBILITATION_SIGNS = {
    "Sun": "Libra","Moon": "Scorpio","Mars": "Cancer",
    "Mercury": "Pisces","Jupiter": "Capricorn",
    "Venus": "Virgo","Saturn": "Aries"
}

NAKSHATRA_NAMES = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra",
    "Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni",
    "Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha",
    "Mula","Purva Ashadha","Uttara Ashadha","Shravana",
    "Dhanishta","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati"
]

NAKSHATRA_LORDS = [
    "Ketu","Venus","Sun","Moon","Mars","Rahu",
    "Jupiter","Saturn","Mercury"
]

# -----------------------------
# FUNCTIONS
# -----------------------------
def get_house(sign, lagna):
    return (sign - lagna + 12) % 12 + 1

def calc_d9(longitude):
    sign = int(longitude / 30)
    degree = longitude % 30
    part = int(degree / (30/9))
    return (sign * 9 + part) % 12 + 1

def calc_d10(longitude):
    sign_index = int(longitude / 30)
    degree = longitude % 30
    part = int(degree / 3)
    sign_number = sign_index + 1

    if sign_number % 2 == 1:
        d10_index = (sign_index + part) % 12
    else:
        d10_index = (sign_index + 8 + part) % 12

    return d10_index + 1

def calc_nakshatra(longitude):
    nak_size = 13 + 20/60
    pada_size = 3 + 20/60

    nak_index = int(longitude / nak_size)
    nak_name = NAKSHATRA_NAMES[nak_index]
    nak_lord = NAKSHATRA_LORDS[nak_index % 9]

    degree_in_nak = longitude % nak_size
    pada = int(degree_in_nak / pada_size) + 1

    return nak_name, pada, nak_lord

# -----------------------------
# MAIN API
# -----------------------------
@app.post("/generate-chart")
def generate_chart(data: BirthInput):

    try:
        # Geolocation
        geolocator = Nominatim(user_agent="astro_app")
        location = geolocator.geocode(data.City)

        if location is None:
            raise HTTPException(status_code=400, detail="City not found")

        lat = location.latitude
        lon = location.longitude

        # Time conversion
        tz = pytz.timezone("Asia/Kolkata")
        dt_local = tz.localize(datetime.strptime(data.DOB + " " + data.TIME, "%d-%m-%Y %H:%M"))
        dt_utc = dt_local.astimezone(pytz.utc)

        jd = swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            dt_utc.hour + dt_utc.minute / 60.0
        )

        swe.set_sid_mode(swe.SIDM_LAHIRI)

        houses = swe.houses_ex(jd, lat, lon, b'A', swe.FLG_SIDEREAL)
        ascendant = houses[1][0]

        d1_lagna = int(ascendant / 30) + 1
        d9_lagna = calc_d9(ascendant)
        d10_lagna = calc_d10(ascendant)

        d1_data, d9_data, d10_data = [], [], []

        # Planet loop
        for pname, pid in PLANETS.items():

            pos, _ = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL)
            longitude = pos[0]
            speed = pos[3]
            retrograde = speed < 0

            sign = int(longitude / 30) + 1
            sign_name = RASHI_NAMES[sign]
            degree = longitude % 30
            house = get_house(sign, d1_lagna)

            nak, pada, nak_lord = calc_nakshatra(longitude)

            own = pname in OWN_SIGNS and sign_name in OWN_SIGNS[pname]
            exalted = pname in EXALTATION_SIGNS and sign_name == EXALTATION_SIGNS[pname]
            debilitated = pname in DEBILITATION_SIGNS and sign_name == DEBILITATION_SIGNS[pname]

            d1_data.append({
                "Planet": pname,
                "Sign": sign_name,
                "Degree": round(degree,2),
                "House": house,
                "Nakshatra": nak,
                "Pada": pada,
                "Nakshatra Lord": nak_lord,
                "Own_Sign": own,
                "Exalted": exalted,
                "Debilitated": debilitated,
                "Retrograde": retrograde
            })

            d9_sign = calc_d9(longitude)
            d10_sign = calc_d10(longitude)

            d9_data.append({
                "Planet": pname,
                "Navamsa Sign": RASHI_NAMES[d9_sign],
                "House": get_house(d9_sign, d9_lagna)
            })

            d10_data.append({
                "Planet": pname,
                "Dashamsa Sign": RASHI_NAMES[d10_sign],
                "House": get_house(d10_sign, d10_lagna)
            })

        # Rahu & Ketu
        rahu_long = swe.calc_ut(jd, swe.MEAN_NODE, swe.FLG_SIDEREAL)[0][0]
        ketu_long = (rahu_long + 180) % 360

        for pname, longitude in [("Rahu", rahu_long), ("Ketu", ketu_long)]:

            sign = int(longitude / 30) + 1
            sign_name = RASHI_NAMES[sign]
            degree = longitude % 30
            house = get_house(sign, d1_lagna)

            nak, pada, nak_lord = calc_nakshatra(longitude)

            d1_data.append({
                "Planet": pname,
                "Sign": sign_name,
                "Degree": round(degree,2),
                "House": house,
                "Nakshatra": nak,
                "Pada": pada,
                "Nakshatra Lord": nak_lord,
                "Own_Sign": False,
                "Exalted": False,
                "Debilitated": False,
                "Retrograde": True
            })

            d9_sign = calc_d9(longitude)
            d10_sign = calc_d10(longitude)

            d9_data.append({
                "Planet": pname,
                "Navamsa Sign": RASHI_NAMES[d9_sign],
                "House": get_house(d9_sign, d9_lagna)
            })

            d10_data.append({
                "Planet": pname,
                "Dashamsa Sign": RASHI_NAMES[d10_sign],
                "House": get_house(d10_sign, d10_lagna)
            })

        return {
            "d1": {"lagna": RASHI_NAMES[d1_lagna], "planets": d1_data},
            "d9": {"lagna": RASHI_NAMES[d9_lagna], "planets": d9_data},
            "d10": {"lagna": RASHI_NAMES[d10_lagna], "planets": d10_data}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
# import nest_asyncio
# import uvicorn
# nest_asyncio.apply()
# uvicorn.run(app, host="0.0.0.0", port=8000)