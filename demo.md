This is the factorio-cli.

It all started because I play the game. In factorio you want to be as efficient as possible. you are always running around solving bottlenecks and refactoring your assembly lines to accomadate forever increasing demand. I have a programming background. I've always throught it'd be cool to use programming in a game. 

Lots of people have made spreadsheets that map out how many machines of each type you need to build a great factory. But I don't make spreadsheets. I write code.
So I started out with a simple program that would take a recipe in the game and figure out how much of each material was needed to build it. It's a tree like structure, where parts are made out of smaller parts and so on. 

Okay so there's a mod that will extract all the recipes and other data from the game as JSON files. How long will it take to build a rocket? Well, each recipe has a crafting time, and I need to unlock recipes through research, which also takes time... so what if I had a program that kept track of time while I plan out the stages of factory building? Instead of making decisions in real time, what if the game was turn based so I could plan out each move.

OKAY. So graphics programming is hard. I'm more interested in the systems design. What if I could play this game through the terminal? Just text commands. The core actions of the game are crafting items, and placing machines. Build a rocket u win. 

Once you have 100s of auto-assemblers and miners, you lose track of where your resources are going. So I built a dashboard utility that shows how much of each item is being created compared to how much would be created if you had unlimited items available. Actual vs. Potential. You can easily plan ahead because you can
see what the factory will do next. 

I added a Limit command because some items are expensive to make and you don't want to waste your resource on something that's low priority. I'm also adding a way to explicitly set machine priority so you can chose where your resources can funneled into first.

It's a way to understand the game on a deeper level. Build it yourself.
It's a way to bring together your expertise and interests. Use programming tools in a game that you like.
It's a way to get closer to the data. Break out of less portable input formats. Use text.
