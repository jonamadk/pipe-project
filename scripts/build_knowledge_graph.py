"""
Step 2 of the build pipeline: a small, hand-curated knowledge graph over
the same source material used in chunk_documents.py, for GraphRAG-style
retrieval (entity match -> graph traversal -> cited passages).

Extend the graph by adding entries to NODES (entities: pathogens,
parameters, materials, features, guidance documents, evidence) and
EDGES (relations between them). Every edge should cite the chunk id(s)
in data/chunks.json that support it, so GraphRAG answers stay grounded
and citable just like the vector-search path.

In a production PIPE deployment, this extraction step would run
automatically: an LLM pass over each newly ingested document proposes
candidate entities/relations, which a human reviews before they're
merged into the graph. This script is the manually-curated seed for
that pipeline.

Usage:
  python scripts/build_knowledge_graph.py
Writes to: data/kg.json
"""
import json, os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, "data", "kg.json")

NODES = {
  "legionella": {"label":"Legionella spp. (OPPP)", "type":"pathogen",
    "aliases":["legionella","legionnaires","oppp","opportunistic pathogen","opportunistic premise plumbing pathogen"]},
  "mycobacteria": {"label":"Non-tuberculous mycobacteria", "type":"pathogen",
    "aliases":["mycobacteria","mycobacterium"]},
  "heater_setpoint": {"label":"Water Heater Setpoint Temperature", "type":"parameter",
    "aliases":["water heater setpoint","heater setpoint","setpoint temperature","water heater temperature"]},
  "pou_temp": {"label":"Point-of-Use (Faucet) Temperature", "type":"parameter",
    "aliases":["point of use temperature","point-of-use temperature","pou temperature","faucet temperature","tap temperature"]},
  "recirc_temp": {"label":"Recirculation Loop Temperature", "type":"parameter",
    "aliases":["recirculation loop temperature","recirculation temperature","return loop temperature","return loop"]},
  "time_to_tap": {"label":"Time to Tap", "type":"parameter",
    "aliases":["time to tap","time-to-tap"]},
  "residual": {"label":"Residual Disinfectant", "type":"parameter",
    "aliases":["residual disinfectant","chlorine residual","disinfectant residual","residual"]},
  "flushing": {"label":"Flushing", "type":"practice",
    "aliases":["flushing","flush the system","flush frequency"]},
  "water_age": {"label":"Water Age / Stagnation", "type":"condition",
    "aliases":["water age","stagnation","residence time","stagnant water","low demand"]},
  "tmv": {"label":"Thermostatic Mixing Valve (TMV)", "type":"feature",
    "aliases":["thermostatic mixing valve","tmv","mixing valve"]},
  "electronic_faucets": {"label":"Electronic (Automatic) Faucets", "type":"feature",
    "aliases":["electronic faucet","automatic faucet","electronic faucets"]},
  "shower_hoses": {"label":"Flexible Shower Hoses", "type":"feature",
    "aliases":["flexible shower hose","shower hose"]},
  "copper_pipe": {"label":"Copper Pipe", "type":"material", "aliases":["copper pipe","copper"]},
  "pvc_pipe": {"label":"PVC Pipe", "type":"material", "aliases":["pvc pipe","pvc"]},
  "pex_pipe": {"label":"PEX Pipe", "type":"material", "aliases":["pex pipe","pex"]},
  "scalding": {"label":"Scalding Risk", "type":"hazard", "aliases":["scalding","scald risk","burn risk"]},
  "chloramine": {"label":"Chloramine", "type":"chemical", "aliases":["chloramine","chloramines"]},
  "chlorine": {"label":"Chlorine", "type":"chemical", "aliases":["chlorine","free chlorine"]},
  "who_2007": {"label":"WHO 2007 (Legionella and the Prevention of Legionellosis)", "type":"guidance",
    "aliases":["who 2007","world health organization 2007"]},
  "cdc_2003": {"label":"CDC 2003 / HICPAC", "type":"guidance", "aliases":["cdc 2003","hicpac"]},
  "osha_1996": {"label":"OSHA 1996", "type":"guidance", "aliases":["osha","osha 1996"]},
  "nasem_2019": {"label":"NASEM 2019 (National Academies)", "type":"guidance",
    "aliases":["nasem","national academies","national academy"]},
  "egwg_2017": {"label":"European Guidelines Working Group 2017", "type":"guidance",
    "aliases":["european guidelines","egwg"]},
  "ipc_2015": {"label":"International Plumbing Code 2015", "type":"guidance",
    "aliases":["international plumbing code","ipc"]},
  "field_survey_2022": {"label":"2022 Field Survey of 41 Facility Managers", "type":"evidence",
    "aliases":["survey","facility managers","field survey","actual compliance","real buildings"]},
}

EDGES = [
  {"from":"water_age","relation":"promotes_growth_of","to":"legionella","note":"Loss of residual disinfectant over extended residence time enables OPPP growth.","chunks":["c13","c26"]},
  {"from":"flushing","relation":"controls","to":"water_age","note":"Flushing brings in fresh residual disinfectant and reduces stagnation.","chunks":["c13","c20"]},
  {"from":"heater_setpoint","relation":"controls","to":"legionella","note":"Higher setpoint temperature suppresses Legionella growth.","chunks":["c15","c31"]},
  {"from":"who_2007","relation":"recommends_min_for","to":"heater_setpoint","note":">60C water heater setpoint.","chunks":["c15"]},
  {"from":"cdc_2003","relation":"recommends_min_for","to":"heater_setpoint","note":">60C water heater.","chunks":["c15"]},
  {"from":"osha_1996","relation":"recommends_min_for","to":"heater_setpoint","note":">60C water heater.","chunks":["c15"]},
  {"from":"nasem_2019","relation":"recommends_min_for","to":"heater_setpoint","note":">60C water heater; >55C hot water.","chunks":["c15"]},
  {"from":"egwg_2017","relation":"recommends_min_for","to":"heater_setpoint","note":"Heater outgoing at least 60C.","chunks":["c15"]},
  {"from":"who_2007","relation":"recommends_min_for","to":"recirc_temp","note":">=50C (122F) in recirculation loop.","chunks":["c32"]},
  {"from":"egwg_2017","relation":"recommends_min_for","to":"recirc_temp","note":">=50C (122F) in recirculation loop.","chunks":["c32"]},
  {"from":"recirc_temp","relation":"controls","to":"legionella","note":"Keeping the loop hot prevents pathogen growth in the distribution system.","chunks":["c32"]},
  {"from":"field_survey_2022","relation":"found_noncompliance_in","to":"heater_setpoint","note":"Only 37% of surveyed buildings met the >=60C/140F guidance; median was 130F/54C.","chunks":["c31"]},
  {"from":"field_survey_2022","relation":"found_noncompliance_in","to":"recirc_temp","note":"Only 25% of surveyed buildings met the >=50C/122F guidance; nearly 80% of high-vulnerability buildings failed.","chunks":["c32"]},
  {"from":"ipc_2015","relation":"recommends_max_for","to":"pou_temp","note":"<43C (110F) as a scald-prevention limit.","chunks":["c15","c28"]},
  {"from":"pou_temp","relation":"controls","to":"scalding","note":"Lower point-of-use temperature reduces scald risk, especially for vulnerable occupants.","chunks":["c28","c33"]},
  {"from":"pou_temp","relation":"conflicts_with","to":"heater_setpoint","note":"Temperatures safe against scalding at the tap (<43-50C) are below the temperatures needed to suppress Legionella upstream (>=60C) - the central design tradeoff in premise plumbing.","chunks":["c28","c33"]},
  {"from":"field_survey_2022","relation":"found_noncompliance_in","to":"pou_temp","note":"94% of buildings met the lenient <50C scald guidance, but median POU temp (110F/43C) is >10F below the level needed for Legionella control - buildings are optimizing for scald safety over pathogen control.","chunks":["c33","c35"]},
  {"from":"tmv","relation":"prevents","to":"scalding","note":"TMVs blend hot and cold water so higher temperatures can be used upstream while protecting users at the tap.","chunks":["c12"]},
  {"from":"tmv","relation":"promotes_growth_of","to":"legionella","note":"TMVs create a favorable temperature zone across their thermal gradient, can fail and mix hot/cold, and biofilms on internal valve materials can harbor pathogens.","chunks":["c12","c34"]},
  {"from":"electronic_faucets","relation":"promotes_growth_of","to":"legionella","note":"Internal materials and lukewarm zones in electronic faucets are associated with Legionella contamination.","chunks":["c11","c34"]},
  {"from":"shower_hoses","relation":"promotes_growth_of","to":"legionella","note":"Flexible shower hoses may leach organic carbon that feeds microbial growth.","chunks":["c11","c34"]},
  {"from":"pvc_pipe","relation":"promotes_growth_of","to":"legionella","note":"PVC pipe may leach organic carbon, which can enhance OPPP growth; treated as a quality-control/testing issue rather than an unavoidable drawback.","chunks":["c12"]},
  {"from":"pex_pipe","relation":"promotes_growth_of","to":"legionella","note":"Similar organic-carbon leaching concern as PVC; NASEM 2019 called for US standards addressing this.","chunks":["c12"]},
  {"from":"copper_pipe","relation":"inhibits","to":"legionella","note":"Copper has antimicrobial properties, but some OPPPs can develop resistance and outcompete other organisms under copper selective pressure.","chunks":["c12"]},
  {"from":"residual","relation":"controls","to":"legionella","note":"Maintaining disinfectant residual was viewed favorably by both SMEs and guidance documents for microbial control.","chunks":["c13","c16"]},
  {"from":"chloramine","relation":"more_effective_against","to":"legionella","note":"Chloramine is more persistent and penetrates biofilms better than chlorine.","chunks":["c13"]},
  {"from":"chloramine","relation":"less_clear_against","to":"mycobacteria","note":"Mycobacteria are generally more resistant to disinfection; chloramine's effect on them is less certain and may even open ecological niches for them.","chunks":["c13"]},
  {"from":"time_to_tap","relation":"indicates","to":"water_age","note":"Time to tap reflects plumbing hydraulics/flow balance, which relates to localized water age even when overall system flushing is adequate.","chunks":["c19","c33"]},
  {"from":"field_survey_2022","relation":"found_noncompliance_in","to":"time_to_tap","note":"27% of buildings had time-to-tap over 60 seconds, exceeding all reference guidance values.","chunks":["c33"]},
]

with open(OUT_PATH, "w") as f:
    json.dump({"nodes": NODES, "edges": EDGES}, f, separators=(',',':'))

print(f"Wrote {OUT_PATH}")
print("nodes:", len(NODES), "edges:", len(EDGES))
