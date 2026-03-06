
import os
import json
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(__file__))

from main import VideoOrchestrator
from core.script_writer import ScriptWriter

# 21 Weird Facts about Dirty Harry (1971) extracted from research
DIRTY_HARRY_FACTS = """
1.  **Original Title and Setting** The initial script for "Dirty Harry" was titled "Dead Right" and was originally set in New York before being changed to Seattle and finally San Francisco.
2.  **Frank Sinatra Almost Starred** Frank Sinatra was originally cast as Harry Callahan but dropped out due to a hand injury sustained during the production of "The Manchurian Candidate," which made it difficult for him to comfortably hold the .44 Magnum.
3.  **Other Big Stars Declined** Several prominent actors, including Burt Lancaster, Paul Newman, Steve McQueen, and Audie Murphy, turned down the role of Harry Callahan, largely due to concerns over the film's violent nature or "right-wing politics."
4.  **Paul Newman's Recommendation** Paul Newman, who disliked the film's politics, recommended Clint Eastwood for the role, believing it would be a good fit for Eastwood's perceived political leanings.
5.  **Eastwood's Condition for Directorial Collaboration** Clint Eastwood only agreed to take the role on the condition that Don Siegel, with whom he had worked on previous films, would direct.
6.  **Eastwood Directed a Scene** Clint Eastwood himself directed the scene where Harry talks a suicidal man down from a ledge, doing so in one day after director Don Siegel fell ill.
7.  **Scorpio's Original Actor Died** Audie Murphy, a World War II hero, was considered for the role of the villain Scorpio but died in a plane crash before accepting the offer.
8.  **Andrew Robinson's "Angel Face" Casting** Andrew Robinson was cast as Scorpio because director Don Siegel wanted someone with an "angelic face" to play against type, making the character even more unsettling.
9.  **Robinson Improvised a Famous Line** Scorpio's line, "My, that's a big one," when Harry reveals his .44 Magnum, was an ad-lib by Andrew Robinson that made the crew laugh, leading to a reshoot, but the line was kept.
10. **Robinson Received Death Threats** Andrew Robinson's chilling portrayal of Scorpio was so convincing that he received actual death threats after the film's release and had to get an unlisted phone number.
11. **Pacifist Actor Played a Killer** Despite his intense performance as Scorpio, Andrew Robinson is a pacifist and initially flinched violently when firing a gun, requiring him to undergo firearms training.
12. **The Zodiac Killer Inspiration** The story of "Dirty Harry" was partly inspired by the real-life Zodiac Killer, who terrorized San Francisco just two years before the film's production.
13. **Harry Callahan's Inspiration** Harry Callahan's character was a composite of three real San Francisco Police Department (SFPD) inspectors, including Dave Toschi, who worked on the Zodiac case.
14. **Cameo by Eastwood's Directorial Debut** During the bank robbery scene, a movie marquee can be seen advertising "Play Misty for Me," Clint Eastwood's directorial debut, which was also released in 1971.
15. **Clint Eastwood Performed His Own Stunts** Clint Eastwood, at 41, performed many of his own stunts, including jumping from a bridge onto a moving school bus.
16. **The .44 Magnum Wasn't Always Real** While Harry's .44 Magnum became iconic, actual .44 Magnum blanks were unavailable in 1971. For firing scenes, a nearly identical Smith & Wesson Model 25 (using .45 caliber rounds) was often used.
17. **Scorpio's WWII Arsenal** Scorpio uses a strange collection of World War II-era weapons, including a Japanese paratrooper rifle, a German MP 40 submachine gun, and a Walther P38 pistol, adding an unsettling layer to his character.
18. **The "Do I Feel Lucky?" Line was Improvised** The famous "Do you feel lucky, punk?" line was improvised by Clint Eastwood on the spot during filming; the original script had a much longer speech.
19. **Child Actors Thought it Was a Comedy** The children on the school bus in the climax were told they were filming a comedy about a pirate to prevent them from being traumatized by the scene's grim reality.
20. **Real-Life Earthquake Delay** A literal earthquake delayed the filming of a rooftop scene, as the ground rumbled and equipment wobbled, causing a brief pause in production.
21. **Film Banned in Several Countries** "Dirty Harry" was banned in multiple countries, including West Germany, and faced censorship in others like the UK, due to concerns that it promoted vigilantism and police brutality.
"""

class SpecializedScriptWriter(ScriptWriter):
    def generate_with_facts(self, topic, style, facts_text, duration):
        """Generate a script using the provided facts."""
        if not self.client:
             return self._generate_fallback(topic, style)
             
        user_prompt = f"""
Create a professional documentary YouTube video script about 'Dirty Harry (1971)' focusing on these 21 Weird Facts:
{facts_text}

Target duration: {duration} seconds.
Total scenes: Around 23 (Intro + 21 Facts + Outro).

REQUIREMENTS:
1. Cover ALL 21 facts provided. Keep each fact concise but engaging.
2. For each fact, create a scene with a specialized search_query to find the RELEVANT movie clip from 'Dirty Harry'.
3. Use 'Dirty Harry' or 'Clint Eastwood' or 'Andrew Robinson' in search queries to ensure they are movie-specific.
4. Total video length should be approximately 4 minutes (240 seconds).

Return ONLY valid JSON in the standard format.
"""
        logger = logging.getLogger("SpecializedScriptWriter")
        logger.info("Calling Gemini API with 21 facts for: %s", topic)
        response = self.client.generate_content(user_prompt)
        raw = response.text.strip()
        import re
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        script = json.loads(raw)
        script["style"] = style
        
        # Backfill
        for i, scene in enumerate(script.get("scenes", []), 1):
            scene.setdefault("scene_id", i)
            scene.setdefault("clip_type", "scene")
            sq = scene.get("search_query", "")
            if "dirty harry" not in sq.lower() and "eastwood" not in sq.lower():
                scene["search_query"] = f"Dirty Harry 1971 {sq}".strip()
        
        return script

def run_specialized_pipeline():
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    orch = VideoOrchestrator()
    # Replace the writer with our specialized one to inject facts
    writer = SpecializedScriptWriter()
    
    topic = "Dirty Harry (1971) 21 Weird Facts"
    style = "documentary"
    duration = 240 # 4 minutes
    
    print(f"Generating script for {topic} with 21 facts...")
    script = writer.generate_with_facts(topic, style, DIRTY_HARRY_FACTS, duration)
    
    # We need to manually run the orchestrator steps if we want to bypass the internal writer.generate
    # Or we can just monkeypatch orch.writer.generate
    orch.writer.generate = lambda t, s, d=180: script 
    
    print("Starting pipeline...")
    final_video = orch.run(topic=topic, style=style)
    
    print(f"\nDone! Video generated at: {final_video}")

if __name__ == "__main__":
    run_specialized_pipeline()
