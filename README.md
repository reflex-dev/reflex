<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg">
  <img alt="Reflex Logo" src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex.svg" width="300px">
</picture>

<hr>

### **✨ Performant, customizable web apps in pure Python. Deploy in seconds. ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![PyPI Downloads](https://static.pepy.tech/badge/reflex)](https://pepy.tech/projects/reflex)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
[![Twitter](https://img.shields.io/twitter/follow/getreflex)](https://x.com/getreflex)

</div>

---

> [!NOTE]
> Build faster with Reflex:
>
> - **[AI Builder](https://build.reflex.dev/)** - Generate full-stack Reflex apps in seconds.
> - **[Agent Toolkit](https://reflex.dev/docs/ai/integrations/agent-toolkit/)** - Connect MCP and Skills to your coding assistant.
> - **[App Management](https://reflex.dev/hosting)** - Deploy and manage your Reflex apps.

---

# Introduction

Reflex is a library to build full-stack web apps in pure Python.

Key features:

- **Pure Python** - Write your app's frontend and backend all in Python, no need to learn Javascript.
- **Full Flexibility** - Reflex is easy to get started with, but can also scale to complex apps.

See our [architecture page](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) to learn how Reflex works under the hood.

## ⚙️ Installation

**Important:** We strongly recommend using a virtual environment to ensure the `reflex` command is available in your PATH.

## 🥳 Create your first app

Create a project, add Reflex, and start the development server with [uv](https://docs.astral.sh/uv/):

```shell
mkdir my_app_name
cd my_app_name
uv init

uv add reflex
uv run reflex init
uv run reflex run
```

You should see your app running at http://localhost:3000.

Now you can modify the source code in `my_app_name/my_app_name.py`. Reflex has fast refreshes so you can see your changes instantly when you save your code.

## 🫧 Example App

Build an image generation app in Python with Reflex: define the UI, manage state in a class, and call an image model from an event handler.

<div align="center">
<video src="https://github.com/user-attachments/assets/aaff28ad-8b3c-43bf-967e-439ee34c8a87" width="900" controls muted poster="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png">
  <a href="https://web.reflex-assets.dev/video/reflex-dalle-video-2x.mp4">
    <img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png" alt="Preview of an image generation app built with Reflex" width="900">
  </a>
</video>
</div>

```python
import reflex as rx
import openai

client = openai.AsyncOpenAI()


class State(rx.State):
    prompt: str = ""
    image_url: str = ""
    processing: bool = False

    @rx.event
    def set_prompt(self, value: str):
        self.prompt = value

    @rx.event
    async def generate(self):
        self.processing = True
        yield
        response = await client.images.generate(
            model="gpt-image-1.5",
            prompt=self.prompt,
        )
        self.image_url = f"data:image/png;base64,{response.data[0].b64_json}"
        self.processing = False


def index():
    return rx.vstack(
        rx.heading("Image Generator"),
        rx.input(placeholder="Enter a prompt...", on_change=State.set_prompt),
        rx.button("Generate", on_click=State.generate, loading=State.processing),
        rx.image(src=State.image_url),
    )


app = rx.App()
app.add_page(index, title="Reflex:Image Generation")
```

## All Thanks To Our Contributors:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>


## 🌐 Web Resources & Interactive Index
- [INDEX18](https://themindplayworks-zh.pages.dev/index18.html)
- [HIDE AND LUIG](https://brainquesteses.pages.dev/hide-and-luig.html)
- [INDEX8](https://eduquests.onrender.com/index8.html)
- [KIDS SUPERMARKET](https://chuyentestss.pages.dev/kids-supermarket.html)
- [2048 RUN GORGEOUS BALLS](https://mindconvert.onrender.com/2048-run-gorgeous-balls.html)
- [CATEGORY ART](https://theeduplays9.pages.dev/category-art.html)
- [CATEGORY RACING DRIVING 3](https://eduquestspt.pages.dev/category-racing-driving-3.html)
- [LOL SURPRISE OMG BB DRIVER](https://mindconvertes.pages.dev/lol-surprise-omg-bb-driver.html)
- [BALLOON POP FRENZY](https://mindconvertjp.pages.dev/balloon-pop-frenzy.html)
- [CATEGORY HAIR](https://mindconvert.onrender.com/category-hair.html)
- [WEAPONS AND RAGDOLLS](https://eduquestspt.pages.dev/weapons-and-ragdolls.html)
- [CATEGORY RUNNING](https://eduquestses.pages.dev/category-running.html)
- [BACK TO SCHOOL UNIFORMS EDITION](https://theplayandlearns-fr.pages.dev/back-to-school-uniforms-edition.html)
- [BEACH SOCCER](https://jangkhangkr.pages.dev/beach-soccer.html)
- [NOOB DRAW PUNCH](https://eduquestspt.pages.dev/noob-draw-punch.html)
- [BANK ROBBERY 3](https://eduquestsfr.pages.dev/bank-robbery-3.html)
- [CATEGORY BIKE](https://mindconvert.onrender.com/category-bike.html)
- [MAGES SECRET](https://themindquests9.pages.dev/mages-secret.html)
- [IDLE FACTORY EMPIRE](https://theskillquests9.pages.dev/idle-factory-empire.html)
- [PUMPKIN CATCHER](https://theknowledgequests9.pages.dev/pumpkin-catcher.html)
- [CATEGORY SURVIVAL GAME](https://thelearningarcades-en.pages.dev/category-survival-game.html)
- [TERMS](https://eduquestses.pages.dev/terms.html)
- [TANKGANK COM](https://mindconvertes.pages.dev/tankgank-com.html)
- [CATEGORY COLLECT565](https://eduquestsfr.pages.dev/category-collect565.html)
- [TERMS](https://jangkhangkr.pages.dev/terms.html)
- [CAT FROM HELL CAT SIMULATOR](https://theeduquests9.pages.dev/cat-from-hell-cat-simulator.html)
- [SORT WORKS NUTS ORDER](https://mindconvertjp.pages.dev/sort-works-nuts-order.html)
- [CATEGORY BOXING](https://thelearnplays9.pages.dev/category-boxing.html)
- [CATEGORY STICKMAN175](https://eduquestspt.pages.dev/category-stickman175.html)
- [FUNNY FEVER HOSPITAL](https://mindconvertjp.pages.dev/funny-fever-hospital.html)
- [SCOOP TOWER](https://thelearnplays9.pages.dev/scoop-tower.html)
- [COFFEE COLOR BLOCKS](https://mindconvertjp.pages.dev/coffee-color-blocks.html)
- [METAXIS](https://skillworld-hi.pages.dev/metaxis.html)
- [GEOMETRY RUSH](https://playworld-es.pages.dev/geometry-rush.html)
- [CATEGORY DRESS UP 2](https://mindconvert.onrender.com/category-dress-up-2.html)
- [HAPPY COLOR](https://mindconvertes.pages.dev/happy-color.html)
- [MOJICON SPRING CONNECT](https://learninggames-fr.pages.dev/mojicon-spring-connect.html)
- [ANIMALON EPIC MONSTERS BATTLE](https://mindconvertes.pages.dev/animalon-epic-monsters-battle.html)
- [SKY BLOCK BOUNCE](https://thelearnplays9.pages.dev/sky-block-bounce.html)
- [FOOTBALL FUN](https://learninggames-fr.pages.dev/football-fun.html)
- [BACKWOODS](https://eduquestsjp.pages.dev/backwoods.html)
- [MINI SHOOTERS](https://knowledgegames-en.pages.dev/mini-shooters.html)
- [TERMS](https://quizzesarena.web.app/terms.html)
- [THEME WORD SEARCH](https://mindconvertfr.pages.dev/theme-word-search.html)
- [ZOMBIE ARENA 2 FURY ROAD](https://mindgames-hi.pages.dev/zombie-arena-2-fury-road.html)
- [PERFECT TIDY](https://mindconvertes.pages.dev/perfect-tidy.html)
- [JUMP MASTER](https://studygames-ru.pages.dev/jump-master.html)
- [VAULT BREAKER](https://braingames-ko.pages.dev/vault-breaker.html)
- [LIGHTS OUT](https://braingames-ko.pages.dev/lights-out.html)
- [CUTE CRAFT LAB](https://skillgames-zh.pages.dev/cute-craft-lab.html)
- [JUNGLE MATCH ADVENTURES](https://knowledgegames-en.pages.dev/jungle-match-adventures.html)
- [CATEGORY LOVE12](https://skillgames-zh.pages.dev/category-love12.html)
- [CATEGORY RPG80](https://theknowledgequests9.pages.dev/category-rpg80.html)
- [CATEGORY TOWER DEFENSE118](https://jangkhangkr.pages.dev/category-tower-defense118.html)
- [MY TINY MARKET](https://mindgames-hi.pages.dev/my-tiny-market.html)
- [FAMILY IDLE FARM BUILD HARVEST](https://schoolgames-es.pages.dev/family-idle-farm-build-harvest.html)
- [CATEGORY CASUAL 17](https://brainquestses.pages.dev/category-casual-17.html)
- [WONDERS OF EGYPT MATCH](https://brainquestsfr.pages.dev/wonders-of-egypt-match.html)
- [CATEGORY FREE SOLITAIRE GAMES](https://thestudyarcades-vi.pages.dev/category-free-solitaire-games.html)
- [BUBBLE SHOOTER POP](https://gamelearning-pt.pages.dev/bubble-shooter-pop.html)
- [CATEGORY ANIMAL216](https://lessonplay-fr.pages.dev/category-animal216.html)
- [JUMPER](https://mindconvertfr.pages.dev/jumper.html)
- [SPRUNKI GETS SURGERY](https://braingames-ko.pages.dev/sprunki-gets-surgery.html)
- [CATEGORY STICKMAN 3](https://jangkhangkr.pages.dev/category-stickman-3.html)
- [INDEX10](https://eduquestses.pages.dev/index10.html)
- [JIGSAW CARDS DAILY PUZZLES](https://mindconvertfr.pages.dev/jigsaw-cards-daily-puzzles.html)
- [KICK LOSER](https://playcampus-ko.pages.dev/kick-loser.html)
- [OBBY PRISON CRAFT ESCAPE](https://eduquestsfr.pages.dev/obby-prison-craft-escape.html)
- [BRAIN FIND CAN YOU FIND IT](https://learninggames-fr.pages.dev/brain-find-can-you-find-it.html)
- [KUZBASS HORROR](https://mindconvert.pages.dev/kuzbass-horror.html)
- [LOGIC BLAST EXPLORER](https://schoolgames-es.pages.dev/logic-blast-explorer.html)
- [GUN EVOLUTION](https://thestudyquests9.pages.dev/gun-evolution.html)
- [PRIVACY](https://skillgames-zh.pages.dev/privacy.html)
- [MERGE FRUIT TIME](https://mindconvertpt.pages.dev/merge-fruit-time.html)
- [DRAW TO CRUSH MONSTER GAME](https://eduquestsjp.pages.dev/draw-to-crush-monster-game.html)
- [CATEGORY CUTE](https://learninggames-fr.pages.dev/category-cute.html)
- [MINER CAT 4](https://mindgames-hi.pages.dev/miner-cat-4.html)
- [GUN SHOOTING GAMES SNIPER 3D](https://mindconvertpt.pages.dev/gun-shooting-games-sniper-3d.html)
- [CATEGORY POINT AND CLICK124](https://mindconvert.onrender.com/category-point-and-click124.html)
- [CATEGORY CASUAL 2](https://edugames-ja.pages.dev/category-casual-2.html)
- [CATEGORY WEBGAME](https://jangkhangkr.pages.dev/category-webgame.html)
- [ASYLUM BALDI GRANNY SLENDER](https://mindconvertes.pages.dev/asylum-baldi-granny-slender.html)
- [CATEGORY WATER39](https://gamelearning-pt.pages.dev/category-water39.html)
- [YES OR NO CHALLENGE RUN](https://playworld-es.pages.dev/yes-or-no-challenge-run.html)
- [BREAK BEAT](https://smartclass-ru.pages.dev/break-beat.html)
- [MOTO RACE CITY](https://mindconvert.pages.dev/moto-race-city.html)
- [FEED ME MONSTERS IDLE BATTLE](https://learnclass-zh.pages.dev/feed-me-monsters-idle-battle.html)
- [PRINCESS VALENTINES CRUSH](https://educlass-en.pages.dev/princess-valentines-crush.html)
- [CRYSTAL CONNECT](https://knowledgegames-en.pages.dev/crystal-connect.html)
- [CATEGORY ARENA](https://educlass-en.pages.dev/category-arena.html)
- [CARS MERGE](https://quizzesarena.onrender.com/cars-merge.html)
- [TWO CARTS DOWNHILL](https://mindgames-hi.pages.dev/two-carts-downhill.html)
- [FURY TANKS](https://brainquestsfr.pages.dev/fury-tanks.html)
- [HIDDEN OBJECT EMILYS CASE](https://jangkhangkr.pages.dev/hidden-object-emilys-case.html)
- [POLITON](https://brainquestsfr.pages.dev/politon.html)
- [BUBBLE SHOOTER REMASTERED](https://mindconvertjp.pages.dev/bubble-shooter-remastered.html)
- [CATEGORY COOKING46](https://edugames-ja.pages.dev/category-cooking46.html)
- [MERGE BRICK BREAKER](https://quizzesarena.onrender.com/merge-brick-breaker.html)
- [BOUNCE DUNK BASKETBALL](https://mindgames-hi.pages.dev/bounce-dunk-basketball.html)
- [FRUIT JAM MERGE PUZZLE GAME](https://learnclass-zh.pages.dev/fruit-jam-merge-puzzle-game.html)
- [CLICKER HERO](https://jangkhangkr.pages.dev/clicker-hero.html)
- [AGARIO](https://eduquestkr.pages.dev/agario.html)
- [IDLE ANIMAL ANATOMY](https://educlass-en.pages.dev/idle-animal-anatomy.html)
- [PET DOCTOR BUSINESS TYCOON PET CARE GAME](https://eduquestspt.pages.dev/pet-doctor-business-tycoon-pet-care-game.html)
- [CATEGORY PIXEL313](https://learnclass-zh.pages.dev/category-pixel313.html)
- [BUILD YOUR AQUARIUM](https://learnclass-zh.pages.dev/build-your-aquarium.html)
- [BROTHERFOLLOW ME MERGE MEN](https://eduquestsfr.pages.dev/brotherfollow-me-merge-men.html)
- [SWORD RUN 3D](https://mindgames-hi.pages.dev/sword-run-3d.html)
- [CATEGORY ARMY40](https://themindquests9.pages.dev/category-army40.html)
- [CATEGORY MISSION206](https://edugames-ja.pages.dev/category-mission206.html)
- [CATEGORY PIXEL](https://braingames-ko.pages.dev/category-pixel.html)
- [ASMR BEAUTY HOMELESS](https://braingames-ko.pages.dev/asmr-beauty-homeless.html)
- [CATEGORY INCREMENTAL](https://learnclass-zh.pages.dev/category-incremental.html)
- [INDEX7](https://gamelearning-pt.pages.dev/index7.html)
- [THE WHITE ROOM 5](https://jangkhangkr.pages.dev/the-white-room-5.html)
- [SHOP SORTING 2](https://eduquestspt.pages.dev/shop-sorting-2.html)
- [GT FLYING CAR RACING](https://playworld-es.pages.dev/gt-flying-car-racing.html)
- [CAR CARE REPAIR DUDU MECHANIC](https://eduquestspt.pages.dev/car-care-repair-dudu-mechanic.html)
- [HIDDEN EASTER EGG HUNT](https://brainquestsfr.pages.dev/hidden-easter-egg-hunt.html)
- [IDLE LUNCH](https://braingames-ko.pages.dev/idle-lunch.html)
- [CAT CUT](https://lessonlab-ko.pages.dev/cat-cut.html)
- [TILE HEX WORLD RED VS BLUE](https://mindconvertjp.pages.dev/tile-hex-world-red-vs-blue.html)
- [SKATE HOOLIGANS](https://lessonquest-ru.pages.dev/skate-hooligans.html)
- [CATEGORY SNAKE](https://themindquests9.pages.dev/category-snake.html)
- [CAT RESCUE](https://learninggames-fr.pages.dev/cat-rescue.html)
- [GRAVITY MATCHER](https://eduquestspt.pages.dev/gravity-matcher.html)
- [INDEX23](https://skillgames-zh.pages.dev/index23.html)
- [CATEGORY JUMP SCARE21](https://braingames-ko.pages.dev/category-jump-scare21.html)
- [GEOMETRY VIBES X BALL](https://thestudyquests9.pages.dev/geometry-vibes-x-ball.html)
- [ZOMBIES WEAPON MERGE 4](https://lessonquest-ru.pages.dev/zombies-weapon-merge-4.html)
