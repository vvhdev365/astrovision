"""
AstroVision AI - Professional Astrology Platform
Real astronomical calculations + AI interpretations
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import math
from functools import lru_cache

# Swiss Ephemeris for accurate calculations
try:
    import swisseph as swe
    SWISS_EPHEMERIS_AVAILABLE = True
except ImportError:
    SWISS_EPHEMERIS_AVAILABLE = False
    print("⚠️ Swiss Ephemeris not available")

# AI Clients (multiple providers for redundancy)
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")  # anthropic, openai, or groq

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
        print("⚠️ No AI provider configured")
except Exception as e:
    AI_AVAILABLE = False
    print(f"⚠️ AI client initialization failed: {e}")

app = FastAPI(
    title="AstroVision AI",
    description="Professional astrology with real calculations + AI",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= ASTROLOGICAL CONSTANTS =============

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

QUALITY_MAP = {
    "Cardinal": ["Aries", "Cancer", "Libra", "Capricorn"],
    "Fixed": ["Taurus", "Leo", "Scorpio", "Aquarius"],
    "Mutable": ["Gemini", "Virgo", "Sagittarius", "Pisces"]
}

RULING_PLANETS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune"
}

# Professional astrologer system prompt
ASTROLOGER_SYSTEM_PROMPT = """You are a professional astrologer with expertise in:
- Traditional astrology (Ptolemy, William Lilly)
- Modern psychological astrology (Jung, Dane Rudhyar)
- Evolutionary astrology (Jeffrey Wolf Green)
- Hellenistic techniques

Your interpretations are:
1. SPECIFIC to the person's chart (never generic)
2. ACTIONABLE (what to do, not just predictions)
3. EMPOWERING (focus on growth and free will)
4. NUANCED (acknowledge complexity)
5. EVIDENCE-BASED (reference actual planetary positions)

You NEVER:
- Make fearful predictions
- Give absolute statements
- Use vague platitudes
- Ignore individual context

Format your responses as clear, insightful guidance that helps the person understand and work with the current energies."""

# ============= HELPER FUNCTIONS =============

def get_sign_from_degree(degree: float) -> str:
    """Convert ecliptic longitude to zodiac sign"""
    degree = degree % 360
    sign_index = int(degree / 30)
    return ZODIAC_SIGNS[sign_index]

def get_degree_in_sign(degree: float) -> float:
    """Get degree within sign (0-30)"""
    return degree % 30

def get_element(sign: str) -> str:
    """Get element for a sign"""
    for element, signs in ELEMENT_MAP.items():
        if sign in signs:
            return element
    return "Unknown"

def get_quality(sign: str) -> str:
    """Get quality/modality for a sign"""
    for quality, signs in QUALITY_MAP.items():
        if sign in signs:
            return quality
    return "Unknown"

# ============= REAL ASTRONOMICAL CALCULATIONS =============

@lru_cache(maxsize=128)
def calculate_daily_transits(date_str: str) -> Dict:
    """Calculate exact planetary positions for a given date (cached)"""
    
    if not SWISS_EPHEMERIS_AVAILABLE:
        return {"error": "Swiss Ephemeris not available"}
    
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    jd = swe.julday(dt.year, dt.month, dt.day, 12.0)  # Noon
    
    planets = {}
    planet_ids = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
        "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN, "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
    }
    
    for planet_name, planet_id in planet_ids.items():
        pos = swe.calc_ut(jd, planet_id)[0][0]  # Longitude
        sign = get_sign_from_degree(pos)
        degree = get_degree_in_sign(pos)
        
        planets[planet_name] = {
            "sign": sign,
            "degree": round(degree, 2),
            "absolute_degree": round(pos, 4),
            "element": get_element(sign),
            "symbol": PLANET_SYMBOLS.get(planet_name, "")
        }
    
    return planets

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
            
            # Calculate angle
            angle = abs(pos1 - pos2)
            if angle > 180:
                angle = 360 - angle
            
            # Check for aspects
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

def calculate_houses(jd: float, lat: float, lng: float) -> Dict:
    """Calculate house cusps using Placidus system"""
    
    if not SWISS_EPHEMERIS_AVAILABLE:
        return {}
    
    houses_cusps, ascmc = swe.houses(jd, lat, lng, b'P')  # Placidus
    
    houses = {}
    for i in range(12):
        house_degree = houses_cusps[i]
        houses[i+1] = {
            "sign": get_sign_from_degree(house_degree),
            "degree": round(get_degree_in_sign(house_degree), 2),
            "absolute_degree": round(house_degree, 2)
        }
    
    return {
        "houses": houses,
        "ascendant": {
            "sign": get_sign_from_degree(ascmc[0]),
            "degree": round(get_degree_in_sign(ascmc[0]), 2)
        },
        "midheaven": {
            "sign": get_sign_from_degree(ascmc[1]),
            "degree": round(get_degree_in_sign(ascmc[1]), 2)
        }
    }

# ============= AI INTERPRETATION FUNCTIONS =============

def generate_ai_response(prompt: str, system_prompt: str = ASTROLOGER_SYSTEM_PROMPT) -> str:
    """Generate AI interpretation using configured provider"""
    
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
    """Format transit data for AI consumption"""
    
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
            "swiss_ephemeris": SWISS_EPHEMERIS_AVAILABLE,
            "ai_powered": AI_AVAILABLE,
            "ai_provider": AI_PROVIDER if AI_AVAILABLE else None,
            "ai_model": AI_MODEL if AI_AVAILABLE else None
        },
        "capabilities": {
            "real_transits": "NASA-level accuracy (Swiss Ephemeris)",
            "ai_interpretations": "Professional astrologer quality",
            "personalization": "Natal chart + daily transits",
            "chat": "Conversational AI astrologer"
        }
    }

@app.get("/api/transits/today")
async def get_todays_transits():
    """Get today's planetary positions"""
    
    today = datetime.now().strftime("%Y-%m-%d")
    planets = calculate_daily_transits(today)
    
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
    
    # Get today's real transits
    today = datetime.now().strftime("%Y-%m-%d")
    planets = calculate_daily_transits(today)
    
    if "error" in planets:
        raise HTTPException(status_code=500, detail=planets["error"])
    
    aspects = calculate_aspects(planets)
    transit_summary = format_transits_for_ai(planets, aspects)
    
    # Generate AI interpretation
    prompt = f"""Generate a personalized daily horoscope for {sign} based on these REAL astronomical positions:

{transit_summary}

Provide specific guidance for {sign} considering:
1. How today's transits affect {sign} specifically
2. Actionable advice for career, relationships, personal growth
3. Timing (what to focus on today)
4. Empowering perspective

Keep it concise (150-200 words), insightful, and helpful."""

    ai_interpretation = generate_ai_response(prompt)
    
    # Calculate lucky numbers from planetary degrees
    lucky_numbers = [
        int(planets["Sun"]["degree"]) % 10,
        int(planets["Moon"]["degree"]) % 10,
        int(planets["Venus"]["degree"]) % 10,
        ZODIAC_SIGNS.index(sign) + 1
    ]
    
    # Dominant element today
    elements = [p["element"] for p in planets.values()]
    dominant_element = max(set(elements), key=elements.count)
    
    element_colors = {
        "Fire": "Red",
        "Earth": "Green",
        "Air": "Yellow",
        "Water": "Blue"
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
        "calculation_method": "Swiss Ephemeris + AI"
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
        
        if not SWISS_EPHEMERIS_AVAILABLE:
            raise HTTPException(status_code=500, detail="Swiss Ephemeris not available")
        
        # Calculate Julian Day
        jd = swe.julday(birth_dt.year, birth_dt.month, birth_dt.day,
                       birth_dt.hour + birth_dt.minute/60.0)
        
        # Calculate planetary positions
        planets = {}
        planet_ids = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
            "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN, "Uranus": swe.URANUS,
            "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
        }
        
        for planet_name, planet_id in planet_ids.items():
            pos = swe.calc_ut(jd, planet_id)[0][0]
            sign = get_sign_from_degree(pos)
            planets[planet_name] = {
                "sign": sign,
                "degree": round(get_degree_in_sign(pos), 2),
                "element": get_element(sign)
            }
        
        # Calculate houses
        house_data = calculate_houses(jd, lat, lng)
        
        # Calculate aspects
        aspects = calculate_aspects(planets, orb=8)
        
        # Format for AI
        chart_summary = f"""NATAL CHART for {name or 'this person'}:
Born: {date} at {time}
Location: {lat}°, {lng}°

SUN: {planets['Sun']['sign']} {planets['Sun']['degree']}°
MOON: {planets['Moon']['sign']} {planets['Moon']['degree']}°
ASCENDANT: {house_data['ascendant']['sign']} {house_data['ascendant']['degree']}°

PLANETARY PLACEMENTS:
"""
        for planet, data in planets.items():
            if planet not in ['Sun', 'Moon']:
                chart_summary += f"- {planet}: {data['sign']} {data['degree']}°\n"
        
        chart_summary += f"\nMAJOR ASPECTS:\n"
        for aspect in aspects[:10]:  # Top 10 aspects
            chart_summary += f"- {aspect['planet1']} {aspect['aspect']} {aspect['planet2']}\n"
        
        # Generate AI interpretation
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
            "houses": house_data["houses"],
            "ascendant": house_data["ascendant"],
            "midheaven": house_data["midheaven"],
            "aspects": aspects,
            "interpretation": ai_interpretation,
            "ai_powered": AI_AVAILABLE,
            "calculation_method": "Swiss Ephemeris + AI"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chat")
async def chat_with_astrologer(
    question: str,
    natal_chart: Optional[Dict] = None,
    conversation_history: Optional[List[Dict]] = None
):
    """Chat with AI astrologer"""
    
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI service not available")
    
    # Build context
    context = ""
    if natal_chart:
        context += f"\nUSER'S NATAL CHART:\n"
        context += f"Sun: {natal_chart.get('sun', 'Unknown')}\n"
        context += f"Moon: {natal_chart.get('moon', 'Unknown')}\n"
        context += f"Ascendant: {natal_chart.get('ascendant', 'Unknown')}\n"
    
    # Get today's transits
    today = datetime.now().strftime("%Y-%m-%d")
    planets = calculate_daily_transits(today)
    if "error" not in planets:
        aspects = calculate_aspects(planets)
        context += f"\nTODAY'S TRANSITS:\n{format_transits_for_ai(planets, aspects)}"
    
    # Build full prompt
    full_prompt = f"""{context}

USER QUESTION: {question}

Provide a thoughtful, specific answer based on astrological principles and the data above."""

    # Generate response
    response = generate_ai_response(full_prompt)
    
    return {
        "success": True,
        "question": question,
        "answer": response,
        "context_used": bool(natal_chart or context),
        "ai_provider": AI_PROVIDER
    }

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
        "expression_number": {"number": expression, "meaning": "Your natural talents and abilities"},
        "soul_urge_number": {"number": soul_urge, "meaning": "Your heart's deepest desires"},
        "personality_number": {"number": personality, "meaning": "How others perceive you"}
    }

@app.get("/api/compatibility")
async def calculate_compatibility(sign1: str, sign2: str):
    """Zodiac compatibility"""
    
    sign1, sign2 = sign1.capitalize(), sign2.capitalize()
    
    if sign1 not in ZODIAC_SIGNS or sign2 not in ZODIAC_SIGNS:
        raise HTTPException(status_code=400, detail="Invalid zodiac sign")
    
    element1 = get_element(sign1)
    element2 = get_element(sign2)
    quality1 = get_quality(sign1)
    quality2 = get_quality(sign2)
    
    score = 50
    
    if element1 == element2:
        score += 30
    elif (element1 in ["Fire", "Air"] and element2 in ["Fire", "Air"]) or \
         (element1 in ["Earth", "Water"] and element2 in ["Earth", "Water"]):
        score += 20
    
    if quality1 == quality2:
        score += 10
    
    rating = "Excellent Match" if score >= 80 else "Very Compatible" if score >= 65 else "Moderate Compatibility" if score >= 50 else "Challenging Match"
    
    return {
        "success": True,
        "sign1": sign1,
        "sign2": sign2,
        "compatibility_score": score,
        "rating": rating,
        "analysis": f"{sign1} ({element1}) and {sign2} ({element2}) have {score}% compatibility.",
        "element_harmony": element1 == element2
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "swiss_ephemeris": SWISS_EPHEMERIS_AVAILABLE,
        "ai_available": AI_AVAILABLE,
        "ai_provider": AI_PROVIDER if AI_AVAILABLE else None
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
