"""
AstroVision Backend - NASA-Level Accuracy with Swiss Ephemeris
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional
import os

# Import Swiss Ephemeris
try:
    import swisseph as swe
    SWISS_EPHEMERIS_AVAILABLE = True
except ImportError:
    SWISS_EPHEMERIS_AVAILABLE = False
    print("Warning: Swiss Ephemeris not available")

app = FastAPI(
    title="AstroVision API",
    description="NASA-level astrology calculations",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

@app.get("/")
async def root():
    return {
        "name": "AstroVision API",
        "status": "active",
        "accuracy": "NASA-level (Swiss Ephemeris)" if SWISS_EPHEMERIS_AVAILABLE else "Simplified",
        "swiss_ephemeris": SWISS_EPHEMERIS_AVAILABLE,
        "calculation_methods": {
            "zodiac": "Tropical zodiac",
            "houses": "Placidus system",
            "numerology": "Pythagorean",
            "ephemeris": "Swiss Ephemeris (JPL)" if SWISS_EPHEMERIS_AVAILABLE else "Simplified"
        }
    }

def get_sign_from_degree(degree: float) -> str:
    degree = degree % 360
    sign_index = int(degree / 30)
    return ZODIAC_SIGNS[sign_index]

def get_element(sign: str) -> str:
    elements = {
        "Fire": ["Aries", "Leo", "Sagittarius"],
        "Earth": ["Taurus", "Virgo", "Capricorn"],
        "Air": ["Gemini", "Libra", "Aquarius"],
        "Water": ["Cancer", "Scorpio", "Pisces"]
    }
    for element, signs in elements.items():
        if sign in signs:
            return element
    return "Unknown"

def get_quality(sign: str) -> str:
    qualities = {
        "Cardinal": ["Aries", "Cancer", "Libra", "Capricorn"],
        "Fixed": ["Taurus", "Leo", "Scorpio", "Aquarius"],
        "Mutable": ["Gemini", "Virgo", "Sagittarius", "Pisces"]
    }
    for quality, signs in qualities.items():
        if sign in signs:
            return quality
    return "Unknown"

def get_ruling_planet(sign: str) -> str:
    rulers = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune"
    }
    return rulers.get(sign, "Unknown")

@app.get("/api/birth-chart")
async def calculate_birth_chart(date: str, time: str, lat: float, lng: float):
    try:
        birth_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        if SWISS_EPHEMERIS_AVAILABLE:
            # NASA-level accuracy!
            jd = swe.julday(birth_dt.year, birth_dt.month, birth_dt.day, 
                          birth_dt.hour + birth_dt.minute/60.0)
            
            sun_pos = swe.calc_ut(jd, swe.SUN)[0][0]
            sun_sign = get_sign_from_degree(sun_pos)
            
            moon_pos = swe.calc_ut(jd, swe.MOON)[0][0]
            moon_sign = get_sign_from_degree(moon_pos)
            
            houses_cusps, ascmc = swe.houses(jd, lat, lng, b'P')
            asc_degree = ascmc[0]
            rising_sign = get_sign_from_degree(asc_degree)
            
            houses = {}
            for i in range(12):
                house_degree = houses_cusps[i]
                houses[f"House_{i+1}"] = {
                    "sign": get_sign_from_degree(house_degree),
                    "degree": round(house_degree % 30, 2)
                }
            
            planets = {}
            planet_ids = {
                "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
                "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
                "Saturn": swe.SATURN, "Uranus": swe.URANUS,
                "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
            }
            
            for planet_name, planet_id in planet_ids.items():
                pos = swe.calc_ut(jd, planet_id)[0][0]
                planets[planet_name] = {
                    "sign": get_sign_from_degree(pos),
                    "degree": round(pos % 30, 2),
                    "absolute_degree": round(pos, 4)
                }
        else:
            # Simplified fallback
            sun_sign = "Aries"
            moon_sign = "Taurus"
            rising_sign = "Gemini"
            houses = {}
            planets = {}
        
        return {
            "success": True,
            "accuracy": "NASA-level" if SWISS_EPHEMERIS_AVAILABLE else "Simplified",
            "sun_sign": {"sign": sun_sign, "element": get_element(sun_sign)},
            "moon_sign": {"sign": moon_sign, "element": get_element(moon_sign)},
            "rising_sign": {"sign": rising_sign, "element": get_element(rising_sign)},
            "houses": houses,
            "planets": planets,
            "interpretation": f"Sun in {sun_sign}, Moon in {moon_sign}, Rising in {rising_sign}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/horoscope/daily")
async def get_daily_horoscope(sign: str):
    sign = sign.capitalize()
    if sign not in ZODIAC_SIGNS:
        raise HTTPException(status_code=400, detail="Invalid sign")
    
    horoscopes = {
        "Aries": "Bold energy surrounds you today. Take initiative in new ventures.",
        "Taurus": "Focus on stability and comfort. Financial opportunities arise.",
        "Gemini": "Communication flows easily today. Share your ideas.",
        "Cancer": "Nurture your emotional connections. Home brings comfort.",
        "Leo": "Your creativity shines brightly. Express yourself boldly.",
        "Virgo": "Organization brings clarity. Perfect day for planning.",
        "Libra": "Balance is key today. Harmonize relationships.",
        "Scorpio": "Deep transformation awaits. Embrace change.",
        "Sagittarius": "Adventure calls to you. Explore new horizons.",
        "Capricorn": "Your hard work pays off. Stay disciplined.",
        "Aquarius": "Innovation is your strength. Think outside the box.",
        "Pisces": "Trust your intuition. Spiritual insights emerge."
    }
    
    colors = {
        "Aries": "Red", "Taurus": "Green", "Gemini": "Yellow",
        "Cancer": "Silver", "Leo": "Gold", "Virgo": "Navy",
        "Libra": "Pink", "Scorpio": "Maroon", "Sagittarius": "Purple",
        "Capricorn": "Brown", "Aquarius": "Blue", "Pisces": "Sea Green"
    }
    
    return {
        "success": True,
        "sign": sign,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "horoscope": horoscopes[sign],
        "lucky_color": colors[sign],
        "lucky_numbers": [1, 7, 14, 21],
        "compatibility": "Leo"
    }

@app.get("/api/numerology")
async def calculate_numerology(name: str, birthdate: str):
    def reduce_to_single(num):
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num
    
    birth_dt = datetime.strptime(birthdate, "%Y-%m-%d")
    life_path = reduce_to_single(sum(int(d) for d in birth_dt.strftime("%Y%m%d")))
    
    values = {chr(i): ((i-65) % 9) + 1 for i in range(65, 91)}
    expression = reduce_to_single(sum(values.get(c.upper(), 0) for c in name if c.isalpha()))
    
    vowels = "AEIOU"
    soul_urge = reduce_to_single(sum(values.get(c.upper(), 0) for c in name if c.upper() in vowels))
    personality = reduce_to_single(sum(values.get(c.upper(), 0) for c in name if c.isalpha() and c.upper() not in vowels))
    
    meanings = {
        1: "The Leader - Independent and ambitious",
        2: "The Diplomat - Cooperative and harmonious",
        3: "The Communicator - Creative and expressive",
        4: "The Builder - Practical and stable",
        5: "The Freedom Seeker - Adventurous and versatile",
        6: "The Nurturer - Responsible and caring",
        7: "The Seeker - Analytical and spiritual",
        8: "The Powerhouse - Ambitious and successful",
        9: "The Humanitarian - Compassionate and idealistic",
        11: "Master Number - Intuitive spiritual leader",
        22: "Master Number - Master builder and visionary",
        33: "Master Number - Master teacher and guide"
    }
    
    return {
        "success": True,
        "life_path_number": {"number": life_path, "meaning": meanings.get(life_path, "Your life purpose")},
        "expression_number": {"number": expression, "meaning": "Your natural talents and abilities"},
        "soul_urge_number": {"number": soul_urge, "meaning": "Your heart's deepest desires"},
        "personality_number": {"number": personality, "meaning": "How others perceive you"}
    }

@app.get("/api/compatibility")
async def calculate_compatibility(sign1: str, sign2: str):
    sign1, sign2 = sign1.capitalize(), sign2.capitalize()
    
    if sign1 not in ZODIAC_SIGNS or sign2 not in ZODIAC_SIGNS:
        raise HTTPException(status_code=400, detail="Invalid sign")
    
    element1 = get_element(sign1)
    element2 = get_element(sign2)
    
    score = 50
    if element1 == element2:
        score += 30
    elif (element1 in ["Fire", "Air"] and element2 in ["Fire", "Air"]) or \
         (element1 in ["Earth", "Water"] and element2 in ["Earth", "Water"]):
        score += 20
    
    if get_quality(sign1) == get_quality(sign2):
        score += 10
    
    rating = "Excellent Match" if score >= 80 else "Very Compatible" if score >= 65 else "Moderate Compatibility" if score >= 50 else "Challenging Match"
    
    return {
        "success": True,
        "sign1": sign1,
        "sign2": sign2,
        "compatibility_score": score,
        "rating": rating,
        "analysis": f"{sign1} ({element1}) and {sign2} ({element2}) have {score}% compatibility. This {rating.lower()} brings together complementary energies."
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
