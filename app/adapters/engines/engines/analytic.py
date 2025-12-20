# app\adapters\engines\engines\analytic.py
# engines\analytic.py
# File: engines/analytic.py
def render_bio(name, gender, profession, nationality, config):
    # Safe defaults if config is empty
    copula = config.get("copula", "IS")
    art_map = config.get("articles", {})
    article = art_map.get("m", "a") # Default to 'a'
    
    return f"{name} {copula} {article} {profession}. {name} {copula} {nationality}."