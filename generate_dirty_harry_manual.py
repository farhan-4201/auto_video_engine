
import os
import json
import logging
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(__file__))

from main import VideoOrchestrator

# 21 Weird Facts with manual narrations (avg 25-30 words) and search queries
FACTS_PLAN = [
    {
        "fact": "Intro",
        "narration": "Dirty Harry remains one of the most iconic action films in cinema history. But behind the gritty exterior lies a treasure trove of bizarre facts you never knew.",
        "query": "Dirty Harry 1971 opening credits HD"
    },
    {
        "fact": "Original Title",
        "narration": "Fact one. The film wasn't always called Dirty Harry. The original script was titled Dead Right and was initially set in New York before moving to San Francisco.",
        "query": "Dirty Harry 1971 San Francisco scenery"
    },
    {
        "fact": "Frank Sinatra",
        "narration": "Frank Sinatra was the first choice for Harry Callahan. He dropped out because a hand injury made it too difficult to handle the massive 44 Magnum.",
        "query": "Dirty Harry 44 Magnum close up"
    },
    {
        "fact": "Stars Declined",
        "narration": "Burt Lancaster, Paul Newman, and Steve McQueen all turned down the role. They were concerned about the film's intense violence and controversial political themes.",
        "query": "Dirty Harry 1971 trailer clips"
    },
    {
        "fact": "Paul Newman",
        "narration": "Despite disliking the politics, Paul Newman recommended Clint Eastwood for the part. He felt Eastwood's persona was a perfect fit for the no-nonsense inspector.",
        "query": "Clint Eastwood Dirty Harry look"
    },
    {
        "fact": "Eastwood Condition",
        "narration": "Clint Eastwood had one condition: Don Siegel had to direct. The two had built a strong partnership on previous films like Two Mules for Sister Sara.",
        "query": "Don Siegel Dirty Harry director"
    },
    {
        "fact": "Eastwood Directed",
        "narration": "Eastwood actually directed one scene himself! When Siegel fell ill, Clint took over to film the sequence where Harry talks down a suicidal man.",
        "query": "Dirty Harry suicide bridge scene"
    },
    {
        "fact": "Scorpio Actor",
        "narration": "Audie Murphy, a famous World War Two hero, was the original choice for the villain Scorpio. Tragically, he died in a plane crash before filming began.",
        "query": "Dirty Harry Scorpio villain"
    },
    {
        "fact": "Andrew Robinson",
        "narration": "Andrew Robinson was cast as Scorpio because of his 'angelic face'. The director wanted a killer who looked completely unexpected and frighteningly normal.",
        "query": "Andrew Robinson Scorpio Dirty Harry"
    },
    {
        "fact": "Improvised Line",
        "narration": "Robinson improvised a classic line. When Harry pulls his gun, Scorpio exclaims, 'My, that's a big one!' The crew laughed, but the line stayed in.",
        "query": "Dirty Harry 44 magnum reveal"
    },
    {
        "fact": "Death Threats",
        "narration": "His performance was so realistic that Robinson received actual death threats. He had to change his phone number to escape the backlash from public anger.",
        "query": "Scorpio Dirty Harry evil laugh"
    },
    {
        "fact": "Pacifist Actor",
        "narration": "In real life, Robinson is a total pacifist. He flinched every time he fired a gun and needed extensive training to look like a hardened killer.",
        "query": "Dirty Harry Scorpio shooting gun"
    },
    {
        "fact": "Zodiac Killer",
        "narration": "The script was directly inspired by the real-life Zodiac Killer. The terrifying events occurred in San Francisco just two years before production started.",
        "query": "Zodiac killer newspaper headlines 1971"
    },
    {
        "fact": "Harry Inspiration",
        "narration": "Harry Callahan was based on real SFPD detectives, including Dave Toschi, who was lead investigator on the actual Zodiac case.",
        "query": "Dirty Harry inspector badge"
    },
    {
        "fact": "Cameo",
        "narration": "Watch closely during the bank robbery. You can see a movie theater marquee advertising Play Misty for Me, which was Eastwood's directorial debut.",
        "query": "Dirty Harry bank robbery scene theater"
    },
    {
        "fact": "Eastwood Stunts",
        "narration": "Eastwood did his own stunts. That jump from a bridge onto a moving school bus? That was really him, performed with no safety harness.",
        "query": "Dirty Harry bridge jump school bus"
    },
    {
        "fact": "Not a 44 Magnum",
        "narration": "They couldn't find 44 Magnum blanks in 1971. In many scenes, Eastwood is actually firing a Smith and Wesson Model 25 with 45 caliber rounds.",
        "query": "Dirty Harry Smith and Wesson"
    },
    {
        "fact": "Scorpio Arsenal",
        "narration": "Scorpio uses a weird mix of World War Two weapons, including Japanese and German guns, to make the character feel more erratic and dangerous.",
        "query": "Scorpio sniper scene Dirty Harry"
    },
    {
        "fact": "Improvised Line 2",
        "narration": "The legendary 'Do I feel lucky?' speech was partially improvised by Eastwood. The original script had a much longer and more technical monologue.",
        "query": "Dirty Harry Do I feel lucky punk"
    },
    {
        "fact": "Comedy Prank",
        "narration": "The child actors on the school bus were told they were filming a comedy about pirates to keep them from being scared during the tense climax.",
        "query": "Dirty Harry school bus scene"
    },
    {
        "fact": "Earthquake",
        "narration": "Filming was delayed by a literal earthquake! During a rooftop sequence, the ground shook so hard that production had to halt for safety.",
        "query": "Dirty Harry rooftop sniper"
    },
    {
        "fact": "Banned",
        "narration": "Dirty Harry was banned in several countries upon release. Critics feared it promoted vigilante justice and police brutality during a sensitive political era.",
        "query": "Dirty Harry 1971 controversial"
    },
    {
        "fact": "Outro",
        "narration": "From improvised lines to real-life inspirations, Dirty Harry is a masterpiece of gritty cinema. Thanks for watching. Like and subscribe for more film facts.",
        "query": "Dirty Harry 1971 ending scene"
    }
]

def generate_manual_script():
    scenes = []
    for i, item in enumerate(FACTS_PLAN, 1):
        scenes.append({
            "scene_id": i,
            "type": "intro" if i == 1 else ("outro" if i == len(FACTS_PLAN) else "body"),
            "narration": item["narration"],
            "search_query": item["query"],
            "clip_type": "scene" if i > 1 else "trailer",
            "emotion": "epic",
            "intensity": 0.7,
            "pacing": "medium",
            "camera_move": "static_wide",
            "color_grade": "muted_film",
            "music_cue": "hold",
            "cut_style": "hard_cut",
            "estimated_duration": len(item["narration"].split()) / 2.5 # approx 150 WPM
        })
    
    return {
        "topic": "Dirty Harry 1971 21 Weird Fact",
        "style": "documentary",
        "is_movie": True,
        "director": "Don Siegel",
        "year": "1971",
        "summary": "21 Weird Facts you didn't know about Dirty Harry (1971)",
        "scenes": scenes
    }

def run_pipeline():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Clear old temp clips for this project so fresh build
    project_id = "dirty_harry_1971_21_weird_fact_documentary"
    clips_dir = Path(__file__).parent / "temp" / project_id / "clips"
    if clips_dir.exists():
        shutil.rmtree(clips_dir)
        print(f"Cleared old clips: {clips_dir}")
    
    script = generate_manual_script()
    
    orch = VideoOrchestrator()
    # Inject our manual script — bypass Gemini generation
    orch.writer.generate = lambda t, s: script
    
    print(f"Starting 21 Weird Facts pipeline ({len(script['scenes'])} scenes, documentary style)...")
    final_video = orch.run(
        topic="Dirty Harry 1971 21 Weird Fact",
        style="documentary",
    )
    
    print(f"\nDone! Video generated at: {final_video}")

if __name__ == "__main__":
    run_pipeline()
