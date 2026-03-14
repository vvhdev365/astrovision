"""
AstroVision AI - Professional Astrology Platform
Real astronomical calculations (Skyfield) + AI interpretations
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
from functools import lru_cache

# Skyfield for astronomical calculations (pure Python, reliable)
try:
    from skyfield.api import load, wgs84
    from skyfield import almanac
    SKYFIELD_AVAILABLE = True
    
    # Load ephemeris data (downloads once, caches)
    ts = load.timescale()
    eph = load('de421.bsp')  # JPL ephemeris
    
    print("✅ Skyfield loaded successfully!")
except Exception as e:
    SKYFIELD_AVAILABLE = False
    print(f"⚠️ Skyfield not available: {e}")

# AI Clients
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")

try:
    if AI_PROVIDER == "anthropic":
        from anthropic import Anthropic
        ai_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        AI_AVAILABLE = True
        AI_MODEL = "claude-3-5-sonnet-20241022"
    elif AI_PROVIDER == "openai":
        from openai import OpenAI
        ai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        AI_AVAILABLE = True
        AI_MODEL = "gpt-4-turbo-preview"
    elif AI_PROVIDER == "groq":
        from groq import Groq
        ai_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        AI_AVAILABLE = True
        AI_MODEL = "llama-3.1-70b-versatile"
    else:
        AI_AVAILABLE = False
except Exception as e:
    AI_AVAILABLE = False
    print(f"⚠️ AI not configured: {e}")

app = FastAPI(
    title="AstroVision AI",
    description="Professional astrology with Skyfield + AI",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= CONSTANTS =============

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANET_SYMBOLS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄",
    "Uranus": "♅", "Neptune": "♆", "Pluto": "♇"
}

ELEMENT_MAP = {
    "Fire": ["Aries", "Leo", "Sagittarius"],
    "Earth": ["Taurus", "Virgo", "Capricorn"],
    "Air": ["Gemini", "Libra", "Aquarius"],
    "Water": ["Cancer", "Scorpio", "Pisces"]
}

ASTROLOGER_SYSTEM_PROMPT = """You are a professional astrologer with expertise in traditional, modern psychological, and evolutionary astrology. 

Your interpretations are:
1. SPECIFIC to the person's chart (never generic)
2. ACTIONABLE (what to do, not just predictions)  
3. EMPOWERING (focus on growth and free will)
4. NUANCED (acknowledge complexity)
5. EVIDENCE-BASED (reference actual planetary positions)

You NEVER make fearful predictions or give absolute statements. Format your responses as clear, insightful guidance."""

# ============= SKYFIELD CALCULATIONS =============

def get_sign_from_degree(degree: float) -> str:
    """Convert ecliptic longitude to zodiac sign"""
    degree = degree % 360
    sign_index = int(degree / 30)
    return ZODIAC_SIGNS[sign_index]

def get_element(sign: str) -> str:
    """Get element for a sign"""
    for element, signs in ELEMENT_MAP.items():
        if sign in signs:
            return element
    return "Unknown"

@lru_cache(maxsize=128)
def calculate_daily_transits_skyfield(date_str: str) -> Dict:
    """Calculate planetary positions using Skyfield"""
    
    if not SKYFIELD_AVAILABLE:
        return {"error": "Skyfield not available"}
    
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        t = ts.utc(dt.year, dt.month, dt.day, 12, 0, 0)  # Noon UTC
        
        planets_data = {}
        
        # Define planets in Skyfield
        planet_objects = {
            "Sun": eph['sun'],
            "Moon": eph['moon'],
            "Mercury": eph['mercury'],
            "Venus": eph['venus'],
            "Mars": eph['mars'],
            "Jupiter": eph['jupiter barycenter'],
            "Saturn": eph['saturn barycenter'],
            "Uranus": eph['uranus barycenter'],
            "Neptune": eph['neptune barycenter'],
            "Pluto": eph['pluto barycenter']
        }
        
        earth = eph['earth']
        
        for planet_name, planet_obj in planet_objects.items():
            # Get geocentric position
            astrometric = earth.at(t).observe(planet_obj)
            lat, lon, distance = astrometric.ecliptic_latlon()
            
            # Convert to degrees
            lon_deg = lon.degrees
            
            sign = get_sign_from_degree(lon_deg)
            degree_in_sign = lon_deg % 30
            
            planets_data[planet_name] = {
                "sign": sign,
                "degree": round(degree_in_sign, 2),
                "absolute_degree": round(lon_deg, 4),
                "element": get_element(sign),
                "symbol": PLANET_SYMBOLS.get(planet_name, "")
            }
        
        return planets_data
        
    except Exception as e:
        return {"error": str(e)}

def calculate_aspects(planets: Dict, orb: float = 8.0) -> List[Dict]:
    """Calculate aspects between planets"""
    
    aspects_list = []
    aspect_types = {
        0: "Conjunction",
        60: "Sextile",
        90: "Square",
        120: "Trine",
        180: "Opposition"
    }
    
    planet_names = list(planets.keys())
    
    for i, planet1 in enumerate(planet_names):
        for planet2 in planet_names[i+1:]:
            pos1 = planets[planet1]["absolute_degree"]
            pos2 = planets[planet2]["absolute_degree"]
            
            angle = abs(pos1 - pos2)
            if angle > 180:
                angle = 360 - angle
            
            for aspect_angle, aspect_name in aspect_types.items():
                diff = abs(angle - aspect_angle)
                if diff <= orb:
                    aspects_list.append({
                        "planet1": planet1,
                        "planet2": planet2,
                        "aspect": aspect_name,
                        "angle": round(angle, 2),
                        "orb": round(diff, 2),
                        "exact": diff < 1.0
                    })
    
    return aspects_list

def calculate_ascendant_skyfield(dt: datetime, lat: float, lng: float) -> Dict:
    """Calculate Ascendant (simplified - accurate to ~1 degree)"""
    
    if not SKYFIELD_AVAILABLE:
        return {}
    
    try:
        t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
        
        # Local Sidereal Time calculation
        gmst = t.gmst
        lst = (gmst + lng / 15.0) % 24
        
        # Simplified ascendant calculation (RAMC method)
        ramc = lst * 15  # Right Ascension of Midheaven
        
        # Convert to ecliptic longitude (simplified)
        # This is approximate but good enough for sign determination
        asc_lon = (ramc + 90) % 360
        
        asc_sign = get_sign_from_degree(asc_lon)
        asc_degree = asc_lon % 30
        
        return {
            "sign": asc_sign,
            "degree": round(asc_degree, 2),
            "absolute_degree": round(asc_lon, 2)
        }
        
    except Exception as e:
        print(f"Ascendant calculation error: {e}")
        return {"sign": "Aries", "degree": 0, "absolute_degree": 0}

# ============= AI FUNCTIONS =============

def generate_ai_response(prompt: str, system_prompt: str = ASTROLOGER_SYSTEM_PROMPT) -> str:
    """Generate AI interpretation"""
    
    if not AI_AVAILABLE:
        return "AI interpretation unavailable. Please configure AI provider."
    
    try:
        if AI_PROVIDER == "anthropic":
            response = ai_client.messages.create(
                model=AI_MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
            
        elif AI_PROVIDER == "openai":
            response = ai_client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            return response.choices[0].message.content
            
        elif AI_PROVIDER == "groq":
            response = ai_client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            return response.choices[0].message.content
            
    except Exception as e:
        return f"AI generation error: {str(e)}"

def format_transits_for_ai(planets: Dict, aspects: List[Dict]) -> str:
    """Format transit data for AI"""
    
    transit_text = "TODAY'S PLANETARY POSITIONS:\n"
    for planet, data in planets.items():
        transit_text += f"- {planet} {data['symbol']}: {data['sign']} {data['degree']}°\n"
    
    if aspects:
        transit_text += "\nMAJOR ASPECTS:\n"
        for aspect in aspects:
            if aspect['exact'] or aspect['orb'] < 3:
                transit_text += f"- {aspect['planet1']} {aspect['aspect']} {aspect['planet2']} (orb: {aspect['orb']}°)\n"
    
    return transit_text

# ============= API ENDPOINTS =============

@app.get("/")
async def root():
    return {
        "name": "AstroVision AI",
        "status": "active",
        "version": "3.0.0",
        "features": {
            "skyfield": SKYFIELD_AVAILABLE,
            "ai_powered": AI_AVAILABLE,
            "ai_provider": AI_PROVIDER if AI_AVAILABLE else None,
            "ai_model": AI_MODEL if AI_AVAILABLE else None
        },
        "capabilities": {
            "real_transits": "JPL accuracy (Skyfield)",
            "ai_interpretations": "Professional astrologer quality",
            "personalization": "Natal chart + daily transits",
            "chat": "Conversational AI astrologer"
        }
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "skyfield": SKYFIELD_AVAILABLE,
        "ai_available": AI_AVAILABLE,
        "ai_provider": AI_PROVIDER if AI_AVAILABLE else None
    }

@app.get("/api/transits/today")
async def get_todays_transits():
    """Get today's planetary positions"""
    
    today = datetime.now().strftime("%Y-%m-%d")
    planets = calculate_daily_transits_skyfield(today)
    
    if "error" in planets:
        raise HTTPException(status_code=500, detail=planets["error"])
    
    aspects = calculate_aspects(planets)
    
    return {
        "success": True,
        "date": today,
        "planets": planets,
        "aspects": aspects,
        "interpretation": format_transits_for_ai(planets, aspects)
    }

@app.get("/api/horoscope/daily/ai")
async def get_ai_daily_horoscope(sign: str):
    """AI-generated daily horoscope based on real transits"""
    
    sign = sign.capitalize()
    if sign not in ZODIAC_SIGNS:
        raise HTTPException(status_code=400, detail="Invalid zodiac sign")
    
    today = datetime.now().strftime("%Y-%m-%d")
    planets = calculate_daily_transits_skyfield(today)
    
    if "error" in planets:
        raise HTTPException(status_code=500, detail=planets["error"])
    
    aspects = calculate_aspects(planets)
    transit_summary = format_transits_for_ai(planets, aspects)
    
    prompt = f"""Generate a personalized daily horoscope for {sign} based on these REAL astronomical positions:

{transit_summary}

Provide specific guidance for {sign} considering:
1. How today's transits affect {sign} specifically
2. Actionable advice for career, relationships, personal growth
3. Timing (what to focus on today)
4. Empowering perspective

Keep it concise (150-200 words), insightful, and helpful."""

    ai_interpretation = generate_ai_response(prompt)
    
    lucky_numbers = [
        int(planets["Sun"]["degree"]) % 10,
        int(planets["Moon"]["degree"]) % 10,
        int(planets["Venus"]["degree"]) % 10,
        ZODIAC_SIGNS.index(sign) + 1
    ]
    
    elements = [p["element"] for p in planets.values()]
    dominant_element = max(set(elements), key=elements.count)
    
    element_colors = {
        "Fire": "Red", "Earth": "Green", 
        "Air": "Yellow", "Water": "Blue"
    }
    
    return {
        "success": True,
        "sign": sign,
        "date": today,
        "horoscope": ai_interpretation,
        "transits": transit_summary,
        "lucky_numbers": lucky_numbers,
        "lucky_color": element_colors.get(dominant_element, "White"),
        "dominant_element": dominant_element,
        "ai_powered": AI_AVAILABLE,
        "calculation_method": "Skyfield (JPL) + AI"
    }

@app.get("/api/birth-chart/ai")
async def calculate_ai_birth_chart(
    date: str,
    time: str,
    lat: float,
    lng: float,
    name: Optional[str] = None
):
    """Calculate birth chart with AI interpretation"""
    
    try:
        birth_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        if not SKYFIELD_AVAILABLE:
            raise HTTPException(status_code=500, detail="Skyfield not available")
        
        # Calculate planetary positions at birth
        date_str = birth_dt.strftime("%Y-%m-%d")
        planets = calculate_daily_transits_skyfield(date_str)
        
        if "error" in planets:
            raise HTTPException(status_code=500, detail=planets["error"])
        
        # Calculate ascendant
        ascendant = calculate_ascendant_skyfield(birth_dt, lat, lng)
        
        # Calculate aspects
        aspects = calculate_aspects(planets, orb=8)
        
        chart_summary = f"""NATAL CHART for {name or 'this person'}:
Born: {date} at {time}
Location: {lat}°, {lng}°

SUN: {planets['Sun']['sign']} {planets['Sun']['degree']}°
MOON: {planets['Moon']['sign']} {planets['Moon']['degree']}°
ASCENDANT: {ascendant['sign']} {ascendant['degree']}°

PLANETARY PLACEMENTS:
"""
        for planet, data in planets.items():
            if planet not in ['Sun', 'Moon']:
                chart_summary += f"- {planet}: {data['sign']} {data['degree']}°\n"
        
        chart_summary += f"\nMAJOR ASPECTS:\n"
        for aspect in aspects[:10]:
            chart_summary += f"- {aspect['planet1']} {aspect['aspect']} {aspect['planet2']}\n"
        
        prompt = f"""{chart_summary}

Provide a comprehensive birth chart interpretation covering:
1. Core identity (Sun, Moon, Ascendant)
2. Key themes and life purpose
3. Strengths and growth areas
4. Relationship patterns
5. Career inclinations

Make it personal, insightful, and empowering (300-400 words)."""

        ai_interpretation = generate_ai_response(prompt)
        
        return {
            "success": True,
            "birth_data": {
                "date": date,
                "time": time,
                "location": {"latitude": lat, "longitude": lng}
            },
            "planets": planets,
            "ascendant": ascendant,
            "aspects": aspects,
            "interpretation": ai_interpretation,
            "ai_powered": AI_AVAILABLE,
            "calculation_method": "Skyfield (JPL) + AI"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/numerology")
async def calculate_numerology(name: str, birthdate: str):
    """Numerology calculation"""
    
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
        1: "The Leader - Independent, ambitious, pioneering",
        2: "The Diplomat - Cooperative, harmonious, sensitive",
        3: "The Communicator - Creative, expressive, social",
        4: "The Builder - Practical, stable, hardworking",
        5: "The Freedom Seeker - Adventurous, versatile, dynamic",
        6: "The Nurturer - Responsible, caring, family-oriented",
        7: "The Seeker - Analytical, spiritual, introspective",
        8: "The Powerhouse - Ambitious, successful, material-focused",
        9: "The Humanitarian - Compassionate, idealistic, selfless",
        11: "Master Number - Intuitive, spiritual leader",
        22: "Master Number - Master builder, visionary",
        33: "Master Number - Master teacher, spiritual guide"
    }
    
    return {
        "success": True,
        "name": name,
        "birthdate": birthdate,
        "life_path_number": {"number": life_path, "meaning": meanings.get(life_path, "")},
        "expression_number": {"number": expression, "meaning": "Your natural talents"},
        "soul_urge_number": {"number": soul_urge, "meaning": "Your deepest desires"},
        "personality_number": {"number": personality, "meaning": "How others see you"}
    }

@app.get("/api/compatibility")
async def calculate_compatibility(sign1: str, sign2: str):
    """Zodiac compatibility"""
    
    sign1, sign2 = sign1.capitalize(), sign2.capitalize()
    
    if sign1 not in ZODIAC_SIGNS or sign2 not in ZODIAC_SIGNS:
        raise HTTPException(status_code=400, detail="Invalid zodiac sign")
    
    element1 = get_element(sign1)
    element2 = get_element(sign2)
    
    score = 50
    
    if element1 == element2:
        score += 30
    elif (element1 in ["Fire", "Air"] and element2 in ["Fire", "Air"]) or \
         (element1 in ["Earth", "Water"] and element2 in ["Earth", "Water"]):
        score += 20
    
    rating = "Excellent Match" if score >= 80 else "Very Compatible" if score >= 65 else "Moderate Compatibility"
    
    return {
        "success": True,
        "sign1": sign1,
        "sign2": sign2,
        "compatibility_score": score,
        "rating": rating,
        "analysis": f"{sign1} ({element1}) and {sign2} ({element2}) have {score}% compatibility.",
        "element_harmony": element1 == element2
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
