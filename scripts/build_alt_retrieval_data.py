"""
Step 3a of the build pipeline: a small structured "facts table" extracted
by hand from Table 4 in both papers (guidance thresholds) and the 2022
facility-manager survey results. This backs the "structured retrieval"
strategy: if a question names a known parameter, skip fuzzy search
entirely and return the exact records for that parameter.

Usage:
  python scripts/build_alt_retrieval_data.py
Writes to: data/structured_facts.json, data/compressed_summary.json
"""
import json, os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Each parameter: aliases (for routing/matching) + a list of exact records.
# record.kind is "guidance" (a recommended threshold) or "survey_finding"
# (what was actually observed in the 2022 facility-manager survey).
STRUCTURED_FACTS = {
  "water_heater_setpoint": {
    "label": "Water Heater Setpoint Temperature",
    "aliases": ["water heater setpoint", "heater setpoint", "water heater temperature", "setpoint temperature", "should my water heater", "water heater be set", "water heater set point"],
    "records": [
      {"kind":"guidance", "source":"WHO 2007", "value":">60C", "chunk":"c15"},
      {"kind":"guidance", "source":"CDC 2003", "value":">60C", "chunk":"c15"},
      {"kind":"guidance", "source":"OSHA 1996", "value":">60C", "chunk":"c15"},
      {"kind":"guidance", "source":"NASEM 2019", "value":">60C", "chunk":"c15"},
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":"heater outgoing at least 60C", "chunk":"c15"},
      {"kind":"survey_finding", "source":"2022 facility manager survey (N=35)", "value":"median 130F (54C), range 105-192F; only 37% compliant with >=140F/60C", "chunk":"c31"}
    ]
  },
  "pou_temperature": {
    "label": "Point-of-Use (Faucet) Temperature",
    "aliases": ["point of use temperature", "point-of-use temperature", "pou temperature", "faucet temperature", "tap temperature", "temperature at the tap", "temperature at the faucet"],
    "records": [
      {"kind":"guidance", "source":"International Plumbing Code 2015", "value":"<43C (scald limit)", "chunk":"c15"},
      {"kind":"guidance", "source":"WHO 2011 / IPC 2015", "value":"<110F (<43C)", "chunk":"c31"},
      {"kind":"guidance", "source":"Dept. of Veterans Affairs 2014 / EGWG 2017", "value":"<122-124F (<50-51C)", "chunk":"c31"},
      {"kind":"survey_finding", "source":"2022 facility manager survey (N=36)", "value":"median 110F (43C); 47% meet strict <110F guidance, 94% meet lenient <122-124F guidance, but this is >10F below Legionella-control minimum", "chunk":"c31"}
    ]
  },
  "recirculation_loop_temp": {
    "label": "Recirculation Loop Temperature",
    "aliases": ["recirculation loop temperature", "recirculation temperature", "return loop temperature", "return loop"],
    "records": [
      {"kind":"guidance", "source":"WHO 2007", "value":">=50C (122F)", "chunk":"c15"},
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":">=50C (122F)", "chunk":"c32"},
      {"kind":"survey_finding", "source":"2022 facility manager survey (N=24)", "value":"median 110F (43C); only 25% compliant, ~80% of high-vulnerability buildings non-compliant", "chunk":"c32"}
    ]
  },
  "temperature_loss": {
    "label": "Temperature Loss (Setpoint minus Recirculation Loop)",
    "aliases": ["temperature loss", "temperature drop", "heat loss in plumbing"],
    "records": [
      {"kind":"guidance", "source":"ASPE 2008", "value":"<9F (<5C)", "chunk":"c32"},
      {"kind":"survey_finding", "source":"2022 facility manager survey (N=22)", "value":"median 13F (7C); only 26% compliant", "chunk":"c32"}
    ]
  },
  "time_to_tap": {
    "label": "Time to Tap",
    "aliases": ["time to tap", "time-to-tap"],
    "records": [
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":"50-55C within 1 min at POU", "chunk":"c18"},
      {"kind":"guidance", "source":"NASEM 2019", "value":">=55C within 1 min at distal points", "chunk":"c18"},
      {"kind":"guidance", "source":"ASPE 2003", "value":"10-30 s", "chunk":"c18"},
      {"kind":"survey_finding", "source":"2022 facility manager survey", "value":"49% at 0-30s, 24% at 31-60s, 27% over 60s; 73% compliant with at least two of three reference guidance documents", "chunk":"c32"}
    ]
  },
  "residual_disinfectant": {
    "label": "Residual Disinfectant",
    "aliases": ["residual disinfectant", "chlorine residual", "disinfectant residual", "free chlorine"],
    "records": [
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":"0.2-1 mg/L chlorine at point of delivery", "chunk":"c16"},
      {"kind":"guidance", "source":"CDC 2003 / U.S. EPA 1985", "value":"1-2 mg/L free chlorine", "chunk":"c16"},
      {"kind":"guidance", "source":"WHO 2007", "value":"0.2-0.5 mg/L free chlorine", "chunk":"c16"},
      {"kind":"survey_finding", "source":"2022 facility manager survey", "value":"monitored in only 4-6% of buildings, one of the least-monitored parameters", "chunk":"c30"}
    ]
  },
  "flushing_frequency": {
    "label": "Flushing Frequency",
    "aliases": ["flushing frequency", "flushing", "flush frequency", "flush my", "how often should i flush", "how often to flush"],
    "records": [
      {"kind":"guidance", "source":"UK Department of Health 2017 Part C", "value":"low-flow fixtures at least daily for 1 min", "chunk":"c16"},
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":"once a week", "chunk":"c16"},
      {"kind":"guidance", "source":"Department of Veterans Affairs 2014", "value":"low-flow fixtures twice per week", "chunk":"c16"}
    ]
  },
  "heat_shock": {
    "label": "Heat Shock (Thermal Disinfection)",
    "aliases": ["heat shock", "thermal disinfection", "thermal shock"],
    "records": [
      {"kind":"guidance", "source":"WHO 2007", "value":">=60C, flush 5-10 min", "chunk":"c17"},
      {"kind":"guidance", "source":"WHO 2011", "value":">60C (preferably >70C) and flush", "chunk":"c17"},
      {"kind":"guidance", "source":"CDC 2003", "value":"71-77C, flush >=5 min", "chunk":"c17"},
      {"kind":"guidance", "source":"OSHA 1996", "value":">=70C, flush 5-20 min", "chunk":"c17"},
      {"kind":"guidance", "source":"European Guidelines Working Group 2017", "value":"70-80C for 72h, flush 5 min", "chunk":"c17"},
      {"kind":"guidance", "source":"U.S. EPA 1985", "value":"71C for 72h, flush 15 min", "chunk":"c17"}
    ]
  },
  "shock_chlorination": {
    "label": "Shock Chlorination",
    "aliases": ["shock chlorination", "hyperchlorination"],
    "records": [
      {"kind":"guidance", "source":"Department of Veterans Affairs 2014", "value":">=2 mg/L free chlorine for >=2h and flush; water heater 20-50 mg/L", "chunk":"c17"},
      {"kind":"guidance", "source":"CDC 2003", "value":"flush >=5 min with >=2 mg/L free residual chlorine; water heater 20-50 mg/L", "chunk":"c17"}
    ]
  },
}

with open(os.path.join(DATA_DIR, "structured_facts.json"), "w") as f:
    json.dump(STRUCTURED_FACTS, f, separators=(",", ":"))
print("Wrote structured_facts.json:", len(STRUCTURED_FACTS), "parameters")


# ---------------------------------------------------------------------------
# Step 3b: a compact, hand-written "compressed corpus" - a dense digest of
# the same two papers, covering every major topic in a fraction of the
# original word count. Backs the "memory compression" retrieval strategy:
# when the full corpus is too large to search/pass around cheaply, retrieve
# against this compressed view instead, then (if needed) drill down to the
# cited original chunks.
# ---------------------------------------------------------------------------

COMPRESSED = [
  {
    "id":"d1", "title":"Temperature guidance vs. reality",
    "text":"Guidance consistently recommends water heater setpoint >=60C/140F and recirculation loop >=50C/122F to control Legionella, while scald-safety guidance (e.g. International Plumbing Code) caps point-of-use temperature at <43C/110F. A 2022 survey of 41 facility managers found actual practice skews toward scald safety: median setpoint was only 130F/54C (37% compliant), median recirculation loop only 110F/43C (25% compliant), and median point-of-use temperature 110F/43C, which meets scald guidance but is >10F below the Legionella-control minimum.",
    "source_chunks":["c15","c31","c32","c28"]
  },
  {
    "id":"d2", "title":"The scald-vs-Legionella tradeoff",
    "text":"Higher temperatures suppress Legionella growth but raise scald risk; lower temperatures are scald-safe but favor Legionella. NASEM's comparison: 110F/43C is nearly scald-risk-free but has high Legionella growth potential; 120F/49C causes low-to-moderate scald risk with moderate-to-low Legionella risk. 110F is recommended only where occupants can't remove themselves from hot water (young, elderly, disabled); 120F may be acceptable elsewhere, provided residual, flushing, and hydraulics compensate.",
    "source_chunks":["c33","c27"]
  },
  {
    "id":"d3", "title":"Disinfectant residual and disinfection methods",
    "text":"Free chlorine residual guidance ranges from 0.2-0.5 mg/L (WHO 2007) up to 1-2 mg/L (CDC 2003, EPA 1985). Chloramine is favored over chlorine by both SMEs and guidance documents for persistence and biofilm penetration, but risks nitrification and has unclear effectiveness against mycobacteria (which are generally disinfection-resistant). Heat-shock disinfection guidance ranges widely: WHO recommends >=60C for 5-10 min, CDC 71-77C for 5+ min, EPA 71C for 72 hours plus a 15-min flush. Despite its importance, residual disinfectant was monitored in only 4-6% of surveyed buildings - one of the largest gaps between guidance and practice found in the research.",
    "source_chunks":["c16","c17","c13","c30"]
  },
  {
    "id":"d4", "title":"Flushing and water age",
    "text":"Flushing frequency guidance ranges from daily (UK DoH, low-flow fixtures) to weekly (EGWG 2017) to twice-weekly (VA 2014). Flushing is viewed favorably by both SMEs and guidance documents (12 favorable vs. 3 unfavorable SME mentions) for bringing fresh residual disinfectant, though it can also add nutrients that feed biofilm growth - the optimal frequency remains an identified knowledge gap. High water age (from low demand, infrequently used fixtures, oversized pipes, or building closures) is unanimously viewed negatively, since it lets residual disinfectant decay and enables Legionella growth.",
    "source_chunks":["c16","c13","c20","c5"]
  },
  {
    "id":"d5", "title":"Problematic plumbing features",
    "text":"Thermostatic mixing valves (TMVs), electronic faucets, and flexible shower hoses are the most frequently reported problematic features, especially in high-vulnerability buildings (35%+ prevalence). All three share two risks: internal materials that can promote microbial growth, and a tendency to create lukewarm dead zones. TMVs are especially contested - favorable because they let higher temperatures run upstream while protecting against scalding at the tap, unfavorable because their thermal gradient, potential to fail and mix hot/cold water, and internal biofilms can all promote Legionella growth. TMVs were more often found at individual fixtures (41% of high-vulnerability buildings) than centralized after the heater (6%).",
    "source_chunks":["c11","c12","c28","c34","c37"]
  },
  {
    "id":"d6", "title":"Pipe materials",
    "text":"Copper has antimicrobial properties but some pathogens, including Legionella, can develop resistance and outcompete other organisms under copper selective pressure. PVC and PEX pipe may leach organic carbon that enhances OPPP growth - treated by SMEs as a quality-control/testing issue rather than an unavoidable drawback. No guidance document makes a blanket pipe-material recommendation; this remains an active knowledge gap, particularly for PEX (addressed by only one of 15 important guidance documents).",
    "source_chunks":["c12","c20"]
  },
  {
    "id":"d7", "title":"Monitoring and management-plan gaps",
    "text":"While over 80% of surveyed buildings monitored water heater setpoint and faucet temperatures, only 59-67% monitored the recirculation loop and just 21-35% monitored the distal tap - a gap precisely at the locations most vulnerable to Legionella growth. Written water management plans existed in only 59% of high-vulnerability and 29% of low-vulnerability buildings, despite CDC toolkit recommendations. No single guidance document was used predominantly by facility managers (ASHRAE was most common in low-vulnerability buildings at 25%, state guidance most common in high-vulnerability buildings at 29%), reflecting that no one document covers everything a facility manager needs.",
    "source_chunks":["c30","c36","c37"]
  },
  {
    "id":"d8", "title":"Guidance document landscape",
    "text":"From a pool of 54 building water quality guidance documents worldwide, 15 were identified as 'important guidance documents' (IGDs) covering the topics SMEs raised. No single IGD covers all 29 design/operational topics identified by SMEs; the 2019 NASEM (National Academies) report is the most comprehensive at 26 of 29 topics, followed by WHO 2007 (15 topics) and CDC 2003 (14 topics). ASHRAE 188 provides a general Legionella risk-management framework without specific numeric thresholds; the CDC's toolkit fills in implementation specifics for ASHRAE 188.",
    "source_chunks":["c9","c10","c14","c21","c37"]
  },
  {
    "id":"d9", "title":"Real-world health burden and case context",
    "text":"US Legionnaires' disease cases increased 5.5-fold from 2000 to 2017 (0.42 to 2.29 per 100,000 population), with outbreaks nearly quadrupling from 2009-2017. The Flint, Michigan crisis (2014) showed how aging plumbing infrastructure can cause both elevated lead exposure and a Legionnaires' disease outbreak simultaneously. Showers are considered one of the highest-risk fixtures due to aerosolization; only 29% of high-vulnerability buildings reported regular showerhead replacement/disinfection, though 65% had self-draining hoses in place.",
    "source_chunks":["c26","c38","c39"]
  },
  {
    "id":"d10", "title":"Key knowledge gaps and study conclusion",
    "text":"Unresolved knowledge gaps include: optimal flushing frequency, optimal residual concentration (balancing OPPP control vs. disinfection byproduct formation), whether TMVs' risks can be resolved with better design/maintenance, chloramine's effectiveness against mycobacteria, tankless vs. tanked water heater water quality, and standardized OPPP characterization methods. Both studies conclude that current US practice prioritizes scald-risk prevention over Legionella control - likely contributing to rising Legionnaires' disease rates - and recommend formal facility-manager training plus development of an evidence-based, building-specific decision support tool (the research lineage PIPE itself continues).",
    "source_chunks":["c20","c35","c39"]
  },
]

with open(os.path.join(DATA_DIR, "compressed_summary.json"), "w") as f:
    json.dump(COMPRESSED, f, separators=(",", ":"))
print("Wrote compressed_summary.json:", len(COMPRESSED), "digest entries")
