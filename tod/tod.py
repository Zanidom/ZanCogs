import time
import random
import discord
import redbot.core
from enum import Enum
from copy import copy
import traceback
from typing import Dict, Optional, Any
from redbot.core import commands, Config

class GameMode(Enum):
    GameMode_Round = 1
    GameMode_Chaos = 2
    GameMode_TrueChaos = 3

class GameState(Enum):
    #Game's not started yet. Default state. If [p]game is used here, it will move to GAME_STARTING
    #if [p]game is used and it is NOT here, throw up a "Game already running!" reply.
    #Beyond this point, every embed has two buttons as a baseline, a Join and Leave button (which adds/removes the UserID from the PlayerList respectively).
    #Additionally, if the game is in GameMode_Chaos, it will add/remove them from the SelectionList.
    NOT_STARTED = 1

    #Player's used [p]game while the game is NotStarted in this channel. Embed pops up showing current settings.
    #Embed has a GameMode button that only works for the command user, which swaps the gamemode between GameMode_Chaos and GameMode_Round.
    #On click, it changes between two icons, depending on which gamestate it is currently representing.
    #Waits for 30 seconds, then evaluates number of players. 1, back to NOT_STARTED and changes this embed to "Not enough players, exiting game."
    #2+, starts the core loop of "Choosing Player" or "Round Starting", depending on which was selected between GameMode_Chaos and GameMode_Round respectively.
    GAME_STARTING = 2

    #If the game is in "Round" mode, at the start of each round it will go here and repopulate the SelectionList with all
    #players currently in the PlayerList before going into ROUND_STARTING.
    #If the game is in Chaos mode, this phase is never reached as players are never removed from the SelectionList.
    ROUND_STARTING = 3

    #Every time it reaches CHOOSING_PLAYER, it creates a new embed ("View") for the turn.
    #From the SelectionList, select one player randomly (ensure that this person is not the last person who went)
    #If there are no players left in the SelectionList, reset it to all players currently in the PlayerList.
    #Then set the chosen player as the interactor for the Choice1/Choice2 buttons on the next embed.
    #Create an embed declaring it's their turn. Move to waiting.
    CHOOSING_PLAYER = 4

    #Await input from the chosen player. Additionally, has a skip button (once per player, bool, toggles on click (voted to skip/un-voted to skip)).
    #If # skips >= 0.5 * total players, edit embed to say "Players voted to skip [player]."
    #Then, change gamestate to CHOOSING_PLAYER.
    #On Choice1/Choice2 button push from the related player, set CurrentChoice to <choice> and change game to PICKER_CHOSEN_AWAITING_INPUT.
    #Create a new embed saying <Player> has chosen <choice>, awaiting input from <Chooser>, has skip button
    #<Chooser> is selected from the PlayerList, and gets an embed asking them to type something.
    WAITING_FOR_PLAYER = 5

    #Await input from the Chooser. Continue to process skips from other players.
    #If # skips >= 0.5x total players, edit embed to say "Players voted to skip [chooser]."
    #Then, pick a new Chooser, create a new embed for the new chooser and continue in this state.
    #Once receiving input from the Chooser, move to INPUT_GIVEN
    PLAYER_HAS_CHOSEN_AWAITING_INPUT = 6
    
    #Create an embed for "Choice complete?" with a Yes and No button, receptive only to the previous Chooser.
    #Continue to process skips as before.
    #If yes is clicked, the Picker's score increases by (1/2, depending on Choice1/Choice2).
    #Regardless of Yes/No, move to INPUT_COMPLETE
    INPUT_GIVEN = 7

    #If we're in GameMode_Round, remove Player from the SelectionList. 
    # Then move to (ROUND_STARTING/CHOOSING_PLAYER), depending on if it's GameMode_Round or GameMode_Chaos 
    INPUT_COMPLETE = 8

    #Game is ending, maybe a player left to trigger it to move here, or maybe something went horribly wrong.
    #Either way, move here, print out the scores, then the game is done.
    GAME_ENDING = 9

class ButtonType(Enum):
    JoinButton = 1
    LeaveButton = 2
    SkipButton = 3
    GameModeButton = 4
    TruthButton = 5
    DareButton = 6
    RandomButton = 7
    PassButton = 8
    FailButton = 9
    AddAnswerButton = 10

class ToDChoice(Enum):
    NoChoiceYet = 1
    Truth = 2
    Dare = 3

class ToDJoinResponse(Enum):
    SuccessfulJoin = 1
    AlreadyPlaying = 2
    GameNotExist = 3
    Error = 4

class ToDLeaveResponse(Enum):
    SuccessfulLeave = 1
    NotPlaying = 2
    GameNotExist = 3
    Error = 4

class ToDSkipResponse(Enum):
    SuccessfulSkipAdded = 1
    SuccessfulSkipRemoved = 2
    NotPlaying = 3
    FailedToggleSkip = 4
    Error = 5

class ToDOption:
    def __init__(self, user:discord.User, text:str):
        print('ToDOption')
        self.user = user
        self.text = text

class ToDLog:
    def __init__(self, user:discord.User, text:str):
        print('ToDLog')
        self.user = user
        self.text = text
        self.time = time.time()


class TruthModal(discord.ui.Modal, title="Truth or Dare"):
    answer = discord.ui.TextInput(label=f"Please input a truth:", style=discord.TextStyle.paragraph, required=True, max_length = 500, placeholder = "Truth")

    async def on_submit(self, interaction:discord.Interaction):
        print('on_submit')
        await interaction.response.defer()

        gameMode = ToDCog.GetGameMode(interaction.channel)
        timeTilChaos = ToDCog.GetTimeUntilChaos(interaction.channel)

        result = await ToDCog.TryAddToD(interaction.channel, self.answer.value, interaction.user)
        if gameMode == GameMode.GameMode_TrueChaos:
            await ToDCog.RefreshView(interaction.channel, timeTilChaos)
        if not result:
            await interaction.followup.send(f"Something went wrong with your input:\n{self.answer.value}\nPlease try again.", ephemeral=True)

class DareModal(discord.ui.Modal, title="Truth or Dare"):
    answer = discord.ui.TextInput(label=f"Please input a dare:", style=discord.TextStyle.paragraph, required=True, max_length = 500, placeholder = "Dare")

    async def on_submit(self, interaction:discord.Interaction):
        print('on_submit')
        await interaction.response.defer()

        gameMode = ToDCog.GetGameMode(interaction.channel)
        timeTilChaos = ToDCog.GetTimeUntilChaos(interaction.channel)
        result = await ToDCog.TryAddToD(interaction.channel, self.answer.value, interaction.user)
        
        if gameMode == GameMode.GameMode_TrueChaos:
            await ToDCog.RefreshView(interaction.channel, timeTilChaos)
        if not result:
            await interaction.followup.send(f"Something went wrong with your input:\n{self.answer.value}\nPlease try again.", ephemeral=True)

class ToDButton(discord.ui.Button):
    def __init__(self, channel:discord.TextChannel, buttonType:ButtonType):
        print('ToDButton')
        emoji = self.GetButtonEmoji(buttonType, channel)
        super().__init__(label=self.GetButtonText(buttonType),emoji=emoji, row=self.GetButtonRow(buttonType))
        self.buttonType = buttonType
        self.channel = channel

    async def JoinButtonPress(self, interaction: discord.Interaction):
        print('JoinButtonPress')
        result = await ToDCog.TryJoinPlayer(interaction.channel, interaction.user)

        if ToDCog.GetGameState(interaction.channel) == GameState.GAME_STARTING:  #refresh the player list
            await self.view.UpdateView(interaction, ToDCog.GetTimeUntilStart(interaction.channel))
        else:
            await interaction.response.defer()

        print (result)
        match result:
            case ToDJoinResponse.SuccessfulJoin:
                name = interaction.user.display_name
                await interaction.followup.send(f"{name} joined.")
            case ToDJoinResponse.AlreadyPlaying:
                await interaction.followup.send("You're already playing!",ephemeral=True)
            case ToDJoinResponse.GameNotExist:
                await interaction.followup.send("There's no current game going on!",ephemeral=True)
            case ToDJoinResponse.Error:
                await interaction.followup.send("Something went wrong. Please @Zan and let him know what you did.",ephemeral=True)
        return

    async def LeaveButtonPress(self, interaction: discord.Interaction):
        print('LeaveButtonPress')
        # First check if player is current player or chooser before removing them
        curPlayer = ToDCog.GetCurrentToDTarget(interaction.channel)
        curChooser = ToDCog.GetCurrentToDChooser(interaction.channel)
        isActivePlayer = (interaction.user == curPlayer or interaction.user == curChooser)
        
        result = await ToDCog.TryLeavePlayer(interaction.channel, interaction.user)
        timeTilStart = ToDCog.GetTimeUntilStart(interaction.channel) 
        
        if ToDCog.GetGameState(interaction.channel) == GameState.GAME_STARTING:  #refresh the player list
            await self.view.UpdateView(interaction, timeTilStart)
        else:
            await interaction.response.defer()

        print (result)
        match result:
            case ToDLeaveResponse.SuccessfulLeave:
                curName = interaction.user.display_name
                # Check game end condition first    
                geResult = await ToDCog.EvaluateGameEnd(interaction.channel)
                
                if geResult == True:
                    print("Outcome 1")
                    await interaction.followup.send(f"{curName} left. Not enough players left, game ending.")
                    await ToDCog.TryEndGame(interaction.channel)
                    return
                else:
                    print("Outcome 2")
                    # If they were active player/chooser, reset game state
                    if isActivePlayer:
                        await interaction.followup.send(f"{curName} left while they were in play - resetting to choosing player")
                        # Set state to INPUT_COMPLETE which will trigger choosing new player
                        await ToDCog.TrySetGameState(interaction.channel, GameState.INPUT_COMPLETE)
                    else:
                        await interaction.followup.send(f"{curName} left.")
            case ToDLeaveResponse.NotPlaying:
                await interaction.followup.send("You're not playing yet!",ephemeral=True)
            case ToDLeaveResponse.GameNotExist:
                await interaction.followup.send("There's no current game going on!",ephemeral=True)
            case ToDLeaveResponse.Error:
                await interaction.followup.send("This should literally never send, please @Zan and let him know what you did.",ephemeral=True)


    async def SkipButtonPress(self, interaction: discord.Interaction):
        print('SkipButtonPress')
        result = await ToDCog.TryToggleSkip(interaction.channel, interaction.user)
        await interaction.response.defer()  #don't update 
        match result:
            case ToDSkipResponse.SuccessfulSkipAdded:
                await interaction.followup.send("Added your vote to skip!",ephemeral=True)
                await ToDCog.ProcessSkipState(interaction.channel)
            case ToDSkipResponse.SuccessfulSkipRemoved:
                await interaction.followup.send("Removed your vote to skip!",ephemeral=True)
            case ToDSkipResponse.FailedToggleSkip:
                await interaction.followup.send("Something went wrong with your skip. Try again or @Zan.",ephemeral=True)
            case ToDSkipResponse.NotPlaying:
                await interaction.followup.send("You're not playing, so you can't vote!",ephemeral=True)
            case ToDSkipResponse.Error:
                await interaction.followup.send("Something went wrong with your skip. Try again or @Zan.",ephemeral=True)
        
    
    async def GameModeButtonPress(self, interaction:discord.Interaction):
        print('GameModeButtonPress')
        temp = await ToDCog.TryNextGameMode(interaction.channel, interaction.user)
        timeTilStart = ToDCog.GetTimeUntilStart(interaction.channel) 

        if not temp:
            await interaction.response.send_message("You didn't make this game! Only the host may change the game mode.",ephemeral=True)
            await self.view.RefreshView(timeTilStart)
            return   
        
        await self.view.UpdateView(interaction, timeTilStart)
        
    async def TruthButtonPress(self, interaction:discord.Interaction):
        print('TruthButtonPress')
        ToDee = ToDCog.GetCurrentToDTarget(interaction.channel)
        if interaction.user != ToDee:
            await interaction.response.send_message("You're not the current target! Wait your turn.",ephemeral=True)
            return
        
        response = await ToDCog.TrySetToDChoice(interaction.channel, interaction.user, ToDChoice.Truth)
        if response:
            response = await ToDCog.TrySetGameState(interaction.channel, GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT)
            if not response:
                await interaction.response.send_message("Something went wrong, please click again",ephemeral=True)
                return
            else:
                return
        else:
            await interaction.response.send_message("Something went wrong, please click again",ephemeral=True)
            return

    async def DareButtonPress(self, interaction:discord.Interaction):
        print('DareButtonPress')
        ToDee = ToDCog.GetCurrentToDTarget(interaction.channel)
        if interaction.user != ToDee:
            await interaction.response.send_message("You're not the current target! Wait your turn.",ephemeral=True)
            return
        
        response = await ToDCog.TrySetToDChoice(interaction.channel, interaction.user, ToDChoice.Dare)
        if response:
            if not (await ToDCog.TrySetGameState(interaction.channel, GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT)):
                await interaction.response.send_message("Something went wrong, please click again",ephemeral=True)
                return
        else:
            await interaction.response.send_message("Something went wrong, please click again",ephemeral=True)
            return

    async def PassButton(self, interaction:discord.Interaction):
        print('PassButton')
        ToDGiver = ToDCog.GetCurrentToDChooser(interaction.channel)
        ToDText = ToDCog.GetChoiceAsString(interaction.channel)
        await interaction.response.defer()

        if interaction.user != ToDGiver:
            await interaction.followup.send(f"You're not the {ToDText} giver! Wait your turn.",ephemeral=True)
            return
        resp = await ToDCog.TryPass(interaction.channel)
        if not resp:
            await interaction.followup.send(f"Something went wrong! Please click again.",ephemeral=True)
            return

    async def FailButton(self, interaction:discord.Interaction):
        print('FailButton')
        ToDGiver = ToDCog.GetCurrentToDChooser(interaction.channel)
        ToDText = ToDCog.GetChoiceAsString(interaction.channel)
        await interaction.response.defer()

        if interaction.user != ToDGiver:
            await interaction.followup.send(f"You're not the {ToDText} giver! Wait your turn.",ephemeral=True)
            return
        resp = await ToDCog.TryFail(interaction.channel)
        if not resp:
            await interaction.followup.send(f"Something went wrong! Please click again.",ephemeral=True)
            return

    async def AddAnswerButton(self, interaction:discord.Interaction):
        print('AddAnswerButton')
        ToDReceiver = ToDCog.GetCurrentToDTarget(interaction.channel)
        ToDGiver = ToDCog.GetCurrentToDChooser(interaction.channel)
        ToDText = ToDCog.GetChoiceAsString(interaction.channel)
        todGameMode = ToDCog.GetGameMode(interaction.channel)
        if todGameMode == GameMode.GameMode_TrueChaos:
            timeTilExpire = ToDCog.GetTimeUntilChaos(interaction.channel)
        else:
            timeTilExpire = None
        
        if interaction.user == ToDReceiver:
            await interaction.response.send_message(f"You're can't give yourself a {ToDText}!",ephemeral=True)
            await ToDCog.RefreshView(self.channel, timeTilExpire)
            return
        if interaction.user != ToDGiver and todGameMode != GameMode.GameMode_TrueChaos:
            await interaction.response.send_message(f"You're not the {ToDText} giver! Wait your turn.",ephemeral=True)
            await ToDCog.RefreshView(self.channel)
            return

        modal = TruthModal() if ToDText == "truth" else DareModal()
        await interaction.response.send_modal(modal)
        await ToDCog.RefreshView(self.channel)
        pass

    async def callback(self, interaction: discord.Interaction):
        print('callback')
        match self.buttonType:
            case ButtonType.JoinButton:
                return await self.JoinButtonPress(interaction)
            case ButtonType.LeaveButton:
                return await self.LeaveButtonPress(interaction)
            case ButtonType.SkipButton:
                return await self.SkipButtonPress(interaction)
            case ButtonType.GameModeButton:
                return await self.GameModeButtonPress(interaction)
            case ButtonType.TruthButton:
                return await self.TruthButtonPress(interaction)
            case ButtonType.DareButton:
                return await self.DareButtonPress(interaction)
            case ButtonType.RandomButton:
                options = [self.DareButtonPress, self.TruthButtonPress]
                await random.choice(options)(interaction)
                return
            case ButtonType.PassButton:
                await self.PassButton(interaction)
                return
            case ButtonType.FailButton:
                await self.FailButton(interaction)
            case ButtonType.AddAnswerButton:
                await self.AddAnswerButton(interaction)
                return
            
    def GetButtonRow(self, buttonType:ButtonType):
        match buttonType:
            case ButtonType.JoinButton: 
                return 0
            case ButtonType.LeaveButton: 
                return 0
            case ButtonType.SkipButton: 
                return 0
            case ButtonType.GameModeButton:
                return 0
            case ButtonType.TruthButton:
                return 1
            case ButtonType.DareButton: 
                return 1
            case ButtonType.RandomButton:
                return 1
            case ButtonType.PassButton:
                return 0
            case ButtonType.FailButton:
                return 0
            case ButtonType.AddAnswerButton:
                return 0


    def GetButtonText(self, buttonType : ButtonType):
        match buttonType:
            case ButtonType.JoinButton: 
                return "Join"
            case ButtonType.LeaveButton: 
                return "Leave"
            case ButtonType.SkipButton: 
                return "Skip"
            case ButtonType.GameModeButton:
                return None
            case ButtonType.TruthButton:
                return "Truth"
            case ButtonType.DareButton: 
                return "Dare"
            case ButtonType.RandomButton:
                return ""
            case ButtonType.PassButton:
                return ""
            case ButtonType.FailButton:
                return ""
            case ButtonType.AddAnswerButton:
                return ""
            
    def GetButtonEmoji(self, buttonType : ButtonType, channel:discord.TextChannel):
        match buttonType:
            case ButtonType.JoinButton:  
                return "➕"
            case ButtonType.LeaveButton:  
                return "➖"
            case ButtonType.SkipButton:   
                return "⏩"
            case ButtonType.GameModeButton:   
                return self.GetGameModeEmoji(channel)
            case ButtonType.TruthButton:   
                return "👄"
            case ButtonType.DareButton:   
                return "🔥"
            case ButtonType.RandomButton:   
                return "🎲"
            case ButtonType.PassButton:   
                return "✅"
            case ButtonType.FailButton:   
                return "⛔"
            case ButtonType.AddAnswerButton:
                return "📝"
    
    def GetGameModeEmoji(self, channel:discord.TextChannel):
        state = ToDCog.GetGameMode(channel)
        match state:
            case GameMode.GameMode_Round:
                return "🔁"
            case GameMode.GameMode_Chaos: 
                return "🎲"
            case GameMode.GameMode_TrueChaos: 
                return "<:elmochaos:910392353204867072>"

class ToDView(discord.ui.View):
    def __init__(self, channel:discord.TextChannel, waitTime:int = None):
        print('ToDView')
        super().__init__(timeout=waitTime)
        self.embed = None
        self.channel = channel
        self.inert = False


    def GetEmbedContent(self):
        print('GetEmbedContent')
        embed = discord.Embed()
        gameMode = ToDCog.GetGameMode(self.channel)
        currentTarget = ToDCog.GetCurrentToDTarget(self.channel)
        currentChooser = ToDCog.GetCurrentToDChooser(self.channel)
        choiceText = ToDCog.GetChoiceAsString(self.channel)
        roundCount = ToDCog.GetRoundCount(self.channel)
        state = ToDCog.GetGameState(self.channel)
        titlePrefix = f"Round {roundCount}" if gameMode is GameMode.GameMode_Round else "Chaos Mode!" if gameMode is GameMode.GameMode_Chaos else "True Chaos Mode!"
        match state:
            case GameState.GAME_STARTING:
                timestampToShow = ToDCog.GetStartTimestamp(self.channel)

                embed.title = "ToD Game Starting!"
                players = ToDCog.GetPlayerList(self.channel)
                playerString = str("")
                for player in players:
                    playerString += player.display_name
                    playerString += '\n'
                gameString = ToDCog.GetGameModeString(self.channel)
                embed.add_field(name="Current player list:",value=playerString)
                embed.add_field(name="Game mode:", value=gameString)

                embed.add_field(name="Game starts", value=f"<t:{timestampToShow}:R>")
                return embed
            case GameState.CHOOSING_PLAYER:
                self.text = f"<@{currentTarget.id}>"
                curName = currentTarget.display_name
                embed.title = titlePrefix
                embed.add_field(name=f"{curName}", value="Please select Truth or Dare:")
                return embed
            case GameState.WAITING_FOR_PLAYER:
                self.text = f"<@{currentTarget.id}>"
                curName = currentTarget.display_name
                embed.title = titlePrefix
                embed.add_field(name=f"{curName}", value="Please select Truth or Dare:")
                return embed            
            case GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
                self.text = f"<@{currentChooser.id}>"
                curName = currentTarget.display_name
                curChooserName = currentChooser.display_name

                embed.title = f"{titlePrefix} - {curName} selected {choiceText}!"
                if (gameMode == GameMode.GameMode_TrueChaos):
                    embed.add_field(name=f"Everyone", value=f"Please all provide a {choiceText} for {curName} using either the prefix \"{choiceText}:\" or the 📝 button below.\nOne will be randomly chosen from your submissions in <t:{int(time.time())+120}:R>.")
                else:
                    embed.add_field(name=f"{curChooserName}", value=f"Please provide a {choiceText} for {curName} using either the prefix \"{choiceText}:\" or the 📝 below.")  
                return embed
            
            case GameState.INPUT_GIVEN:
                self.text = f"<@{currentChooser.id}>, <@{currentTarget.id}>"
                tods = ToDCog.GetCurrentToD(self.channel)
                if tods is None:  
                    currentToD = "N/A, something went wrong."
                else:
                    currentToD = tods.text

                curName = currentTarget.display_name

                curChooserName = currentChooser.display_name

                embed.title = f"{titlePrefix} - {curName} selected {choiceText}!"
                embed.add_field(name=f"{choiceText.title()}:", value=f"{currentToD}\n\n{curChooserName}, please click the ✅ or ⛔ below once {curName} has passed or failed.")
                return embed
            case _:
                return None
   
    async def CreateView(self):
        print('CreateView')
        #First, empty this view.
        self.embed = None
        self.clear_items()

        embedContent = self.GetEmbedContent()
        if embedContent is not None:
            self.embed = embedContent

        gameEnding = ToDCog.GetGameState(self.channel) == GameState.GAME_ENDING

        if ToDCog.GetIsNewRound(self.channel) or gameEnding:
            self.scores = copy(ToDCog.GetScores(self.channel, gameEnding))
            
            #sort dict. not pretty but hey
            {k: v for k, v in sorted(self.scores.items(), key=lambda item: item[1])}

            scoreList = ""
            for key, score in self.scores.items():
                nameAwait = await self.channel.guild.fetch_member(key)
                name = nameAwait.display_name
                scoreList += f"{name}: {score}\n"
            scoreList += '\n\n'
            if scoreList != "":
                self.embed.insert_field_at(0, name="Scores so far:", value=scoreList, inline=False)
            await ToDCog.TryClearIsNewRound(self.channel)

        #Join and leave are on all ToDViews other than the final scoreview that we print so that players have the agency to join and leave as they wish.
        if not gameEnding:
            self.add_item(ToDButton(self.channel,buttonType=ButtonType.JoinButton))
            self.add_item(ToDButton(self.channel,buttonType=ButtonType.LeaveButton))

        mode = ToDCog.GetGameMode(self.channel)
        state = ToDCog.GetGameState(self.channel)
        match state:
            case GameState.GAME_STARTING:
                self.add_item(ToDButton(self.channel, ButtonType.GameModeButton))
                return
            case GameState.CHOOSING_PLAYER:
                if (ToDCog.GetPlayerCount(self.channel) > 2):
                    self.add_item(ToDButton(self.channel, ButtonType.SkipButton))
                self.add_item(ToDButton(self.channel, ButtonType.TruthButton))
                self.add_item(ToDButton(self.channel, ButtonType.DareButton))
                self.add_item(ToDButton(self.channel, ButtonType.RandomButton))
            case GameState.WAITING_FOR_PLAYER:
                if (ToDCog.GetPlayerCount(self.channel) > 2):
                    self.add_item(ToDButton(self.channel, ButtonType.SkipButton))
                self.add_item(ToDButton(self.channel, ButtonType.TruthButton))
                self.add_item(ToDButton(self.channel, ButtonType.DareButton))
                self.add_item(ToDButton(self.channel, ButtonType.RandomButton))
                return
            case GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
                if (ToDCog.GetPlayerCount(self.channel) > 2):
                    self.add_item(ToDButton(self.channel, ButtonType.SkipButton))
                self.add_item(ToDButton(self.channel, ButtonType.AddAnswerButton))
                return
            case GameState.INPUT_GIVEN:
                self.timeout = 60 if mode == GameMode.GameMode_Chaos else None
                if (ToDCog.GetPlayerCount(self.channel) > 2):
                    self.add_item(ToDButton(self.channel, ButtonType.SkipButton))
                self.add_item(ToDButton(self.channel, ButtonType.PassButton))
                self.add_item(ToDButton(self.channel, ButtonType.FailButton))
                return
            
    async def UpdateView(self, interaction: discord.Interaction, timeOut:int = None):
        print('UpdateView')
        await self.CreateView()
        self.timeout = timeOut
        args = self.GetArgs()
        await interaction.response.edit_message(**args)

    async def RefreshView(self, timeOut:int = None):
        print('RefreshView')
        self.timeout = timeOut
        args = self.GetArgs()
        if self.message is not None:
            await self.message.edit(**args)
        else:
            await self.channel.send(**args)

    async def NotEnoughPlayersView(self):
        print('NotEnoughPlayersView')
        self.clear_items()
        self.embed = discord.Embed()
        self.embed.title = "Not enough players, exited ToD."
        args = self.GetArgs()
        await self.message.edit(**args)

    async def SkipView(self):
        print('SkipView')
        self.clear_items()
        self.embed = discord.Embed()
        playerOrChooser = None
        playerOrChooserType = None
        gameState = ToDCog.GetSkippedState(self.channel)
        await ToDCog.TryClearWasSkipped()
        try:
            if gameState == GameState.CHOOSING_PLAYER or gameState == GameState.WAITING_FOR_PLAYER:
                playerOrChooser = ToDCog.GetCurrentToDTarget(self.channel)
                playerOrChooserType = "player "
            else:
                playerOrChooser = ToDCog.GetCurrentToDChooser(self.channel)
                playerOrChooserType = ""

            playerOrChooserName = playerOrChooser.display_name
        except:
            pass
        
        self.embed.insert_field_at(0, name="Skipped!", value=f"Skipped {playerOrChooserType}{playerOrChooserName} by vote")
        self.embed.title = "Skipped"
        args = self.GetArgs()
        try:
            await self.message.edit(**args)
        except:
            pass

    async def MakeInert(self):
        print('MakeInert')
        if (self.inert):    #prevent inertion more than once
            return
        self.inert = True
        self.clear_items()
        self.timeout = None
        args = self.GetArgs()
        await self.message.edit(**args)
        self.stop()

    def GetArgs(self):
        print('GetArgs')
        ret: Dict[str, Optional[Any]] = {"view": self}
        try:
            if self.embed is not None:
                ret["embed"] = self.embed
        except:
            pass
        try:
            if self.text is not None:
                ret["content"] = self.text
        except:
            pass
        return ret

    async def StartView(self, channel:discord.TextChannel):
        print('StartView')
        self.author = ToDCog.GetGameCreator(channel)
        kwargs = self.GetArgs()
        self.message = await channel.send(**kwargs)

    async def on_timeout(self):
        print('on_timeout')        
        state = ToDCog.GetGameState(self.channel)
        match state:
            case GameState.GAME_STARTING:
                players = ToDCog.GetPlayerList(self.channel)
                if len(players) > 1:
                    self.embed.title = "ToD Game Started!"
                    self.embed.set_field_at(2, name="Game Started", value=f"{self.embed.fields[2].value}")
                    await ToDCog.TrySetGameState(self.channel, GameState.ROUND_STARTING)
                else:
                    await ToDCog.TrySetGameState(self.channel, GameState.NOT_STARTED)
                    await self.NotEnoughPlayersView()
                return
            case GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
                curGM = ToDCog.GetGameMode(self.channel)
                if curGM == GameMode.GameMode_TrueChaos:
                    timeTil = ToDCog.GetTimeUntilChaos(self.channel)
                    if timeTil <= 0:
                       await ToDCog.TrySetGameState(self.channel, GameState.INPUT_GIVEN)
                else:
                        await ToDCog.TrySetGameState(self.channel, GameState.INPUT_GIVEN)
                return
            case _:
                pass

class ToDGame:
    def __init__(self, channel: discord.TextChannel, gameMaker:discord.User):
        print('ToDGame')
        self.channel = channel
        self.creator = gameMaker
        self.state = GameState.GAME_STARTING
        self.game_mode = GameMode.GameMode_Round
        self.startTimestamp = int(time.time()) + 30
        self.trueChaosFinishTimestamp = int(time.time())
        self.players = []
        self.selection_list = []
        self.last_player = None
        self.current_player = None
        self.current_chooser = None
        self.current_choice = None
        self.chosenToD = None
        self.skip_votes = []
        self.wasSkipped = False
        self.stateOnSkip = GameState.NOT_STARTED
        self.truthscores = {}  # player_id: score
        self.darescores = {}  # player_id: score
        self.roundCount = 0
        self.todCount = 0
        self.ToDOptions = list()
        self.recentOutcome = None  #false for a fail, true for a pass
        self.isNewRound = False

    async def SpawnView(self, timeout:int = None):
        print('SpawnView')
        self.gameView = ToDView(self.channel, timeout)
        await self.gameView.CreateView()
        await self.gameView.StartView(self.channel)
        await self.gameView.wait()

    async def EndGame(self):
        print('EndGame')
        if (self.state == GameState.GAME_STARTING):
            await self.gameView.on_timeout()
        else:
            await self.gameView.MakeInert()

    async def RoundStarting(self):
        print('RoundStarting')
        self.roundCount += 1
        await self.gameView.RefreshView()
        await self.gameView.MakeInert()
        self.selection_list = copy(self.players)
        self.state = GameState.CHOOSING_PLAYER
        await self.OnStateChange()

    async def ChoosingPlayer(self):
        print('ChoosingPlayer')
        if self.current_player is not None:
            self.last_player = self.current_player

        curSelList = copy(self.selection_list)
        if len(curSelList) > 1:
            try:
                #handles the case where we start a new round and we've freshly repopulated our selection list
                curSelList.remove(self.last_player)
            except:
                pass
        self.current_choice = ToDChoice.NoChoiceYet
        self.current_player = random.choice(curSelList)
        self.state = GameState.WAITING_FOR_PLAYER
        await self.gameView.MakeInert()
        await self.OnStateChange()
        await self.SpawnView()


    async def ChooseChooser(self):
        print('ChooseChooser')
        choicePool = copy(self.players)
        choicePool.remove(self.current_player)
        self.current_chooser = random.choice(choicePool)

    async def PlayerChoseToD(self):
        print('PlayerChoseToD')
        await self.gameView.MakeInert()
        if self.game_mode == GameMode.GameMode_TrueChaos:
            self.trueChaosFinishTimestamp = int(time.time() + 120)
            await self.ChooseChooser()  #prevent error by making this have a value lmao
            await self.SpawnView(120)
        else:
            await self.ChooseChooser()
            await self.SpawnView()

    async def InputGiven(self):
        print('InputGiven')
        if len(self.ToDOptions) == 0:
            await self.gameView.RefreshView(120)
        elif len(self.ToDOptions) == 1:
            self.chosenToD = copy(self.ToDOptions[0])
        else:
            self.chosenToD = copy(random.choice(self.ToDOptions))
        await self.gameView.MakeInert()
        self.ToDOptions.clear()
        await self.SpawnView()
        
    async def InputComplete(self):
        print('InputComplete') 
        if (await self.EvaluateGameEnd()):
            await self.EndGame()
            return True
        
        self.todCount += 1
        if self.wasSkipped:
            try:
                await self.gameView.SkipView()
            except:
                pass
        else:
            await self.gameView.MakeInert()

        #in cases where we skipped here or the user failed, the user won't get any score
        if self.recentOutcome == True:
            match self.current_choice:
                case ToDChoice.Truth:
                    try:
                        self.truthscores[self.current_player.id] += 1
                    except:
                        self.truthscores[self.current_player.id] = 1
                case ToDChoice.Dare:
                    try:
                        self.darescores[self.current_player.id] += 2
                    except:
                        self.darescores[self.current_player.id] = 2
            self.recentOutcome = False
        if (self.game_mode == GameMode.GameMode_Round):
            if (self.current_player in self.selection_list):
                self.selection_list.remove(self.current_player)
            if len (self.selection_list) == 0:
                self.state = GameState.ROUND_STARTING
                self.isNewRound = True
                await self.OnStateChange()
            else:
                self.state = GameState.CHOOSING_PLAYER
                await self.OnStateChange()
        else:
            self.state = GameState.CHOOSING_PLAYER
            if self.todCount >= len(self.players):
                self.roundCount += 1
                self.isNewRound = True
                self.todCount = 0
            await self.OnStateChange()

    async def CheckSkip(self):
        print('CheckSkip')
        areWeSkipping = len(self.skip_votes) >= (len(self.players) * 0.499)
        if (areWeSkipping):
            print("Skipping confirmed")
            self.wasSkipped = True
            self.skip_votes.clear()
            self.stateOnSkip = self.state
            match self.state:
                case GameState.WAITING_FOR_PLAYER:
                    self.state = GameState.INPUT_COMPLETE   #reset to choose a player
                    await self.OnStateChange()
                case GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
                    if self.game_mode == GameMode.GameMode_Chaos:
                        self.state = GameState.INPUT_COMPLETE
                    await self.OnStateChange()
                case GameState.INPUT_GIVEN:
                    self.state = GameState.INPUT_COMPLETE
                    await self.OnStateChange()
                case _:
                    return False
            return True   #returns true if half+ voted to skip
        return False

    async def EvaluateGameEnd(self):
        print('EvaluateGameEnd')
        playerLimit = 1
        if self.state == GameState.GAME_STARTING:
            playerLimit -= 1
        if len(self.players) <= playerLimit:
            return True
        return False

    async def ToggleSkip(self, user:discord.User):
        print('ToggleSkip')
        if user not in self.players:
            return ToDSkipResponse.NotPlaying
        try:
            if user.id in self.skip_votes:
                self.skip_votes.remove(user.id)
                return ToDSkipResponse.SuccessfulSkipRemoved
            else:
                self.skip_votes.append(user.id)
                return ToDSkipResponse.SuccessfulSkipAdded
        except:
            return ToDSkipResponse.Error

    async def OnStateChange(self):
        print('OnStateChange')
        self.skip_votes.clear()
        match self.state:
            case GameState.ROUND_STARTING:
                await self.RoundStarting()
                return
            case GameState.CHOOSING_PLAYER:
                await self.ChoosingPlayer()
                return
            case GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
                await self.PlayerChoseToD()
                return
            case GameState.INPUT_GIVEN:
                await self.InputGiven()
                return
            case GameState.INPUT_COMPLETE:
                await self.InputComplete()
                return
            
class ToDCog(commands.Cog):
    @classmethod
    def __init__(self, bot):
        print('ToDCog')
        self.bot = bot
        self.games = {}  # key: channel.id, value: Game instance

    @classmethod
    def GetGameState(self, channel:discord.TextChannel):
        print('GetGameState')
        return self.games[channel.id].state
    
    @classmethod
    def GetSkippedState(self, channel:discord.TextChannel):
        print('GetSkippedState')
        return self.games[channel.id].stateOnSkip

    @classmethod
    def GetGameModeString(self, channel:discord.TextChannel):
        print('GetGameModeString')
        match ToDCog.GetGameMode(channel):
            case GameMode.GameMode_Round:
                return "Round"
            case GameMode.GameMode_Chaos: 
                return "Chaos"
            case GameMode.GameMode_TrueChaos: 
                return "True Chaos"
            
    @classmethod
    def GetGameMode(self, channel:discord.TextChannel):
        print('GetGameMode')
        return self.games[channel.id].game_mode

    @classmethod
    def GetPlayerList(self, channel:discord.TextChannel):
        print('GetPlayerList')
        return self.games[channel.id].players
    
    @classmethod
    def GetPlayerCount(self, channel:discord.TextChannel):
        print('GetPlayerCount')
        return len(self.games[channel.id].players)

    @classmethod
    def GetGameCreator(self, channel:discord.TextChannel):
        print('GetGameCreator')
        try:
            return self.games[channel.id].creator
        except:
            return None

    @classmethod
    def GetScores(self,channel:discord.TextChannel, includeNotPlaying: bool = False):
        print('GetScores')
        try:
            truthscores = self.games[channel.id].truthscores
            darescores = self.games[channel.id].darescores
            if includeNotPlaying:
                scores = {k: truthscores.get(k, 0) + darescores.get(k, 0) 
                      for k in set(truthscores) | set(darescores)}
            else:
                player_ids = [player.id for player in self.games[channel.id].players]
                scores = {k: truthscores.get(k, 0) + darescores.get(k, 0) 
                      for k in set(truthscores) | set(darescores)
                      if k in player_ids} 
            return scores
        except:
            return None

    @classmethod
    def GetIsNewRound(self, channel:discord.TextChannel):
        print('GetIsNewRound')
        try:
            return self.games[channel.id].isNewRound
        except:
            return None

    @classmethod
    def GetCurrentToDTarget(self, channel:discord.TextChannel):
        print('GetCurrentToDTarget')
        try:
            return self.games[channel.id].current_player
        except:
            return None

    @classmethod
    def GetCurrentToD(self, channel:discord.TextChannel):
        print('GetCurrentToD')
        try:
            return self.games[channel.id].chosenToD
        except:
            return None

    @classmethod
    def GetCurrentToDChooser(self, channel:discord.TextChannel):
        print('GetCurrentToDChooser')
        try:
            return self.games[channel.id].current_chooser
        except:
            return None

    @classmethod
    def GetCurrentSkips(self, channel:discord.TextChannel):
        print('GetCurrentSkips')
        try:
            return self.games[channel.id].skip_votes
        except:
            return None

    @classmethod
    def GetStartTimestamp(self, channel:discord.TextChannel):
        print('GetStartTimestamp')
        return self.games[channel.id].startTimestamp

    @classmethod
    def GetTimeUntilStart(self, channel:discord.TextChannel):
        print('GetTimeUntilStart')
        startTime = self.games[channel.id].startTimestamp
        timeNow = int(time.time())
        timeUntilStart = startTime - timeNow
        return timeUntilStart

    @classmethod
    def GetChaosTimestamp(self, channel:discord.TextChannel):
        print('GetChaosTimestamp')
        return self.games[channel.id].trueChaosFinishTimestamp

    @classmethod
    def GetTimeUntilChaos(self, channel:discord.TextChannel):
        print('GetTimeUntilChaos')
        finTime = self.games[channel.id].trueChaosFinishTimestamp
        timeNow = int(time.time())
        timeUntilStart = finTime - timeNow
        return timeUntilStart

    @classmethod
    def GetChoiceAsString(self, channel:discord.TextChannel):
        print('GetChoiceAsString')
        choice = self.games[channel.id].current_choice
        if choice == ToDChoice.Truth:
            return "truth"
        elif choice == ToDChoice.Dare:
            return "dare"
        else:
            return None

    @classmethod
    def GetRoundCount(self, channel:discord.TextChannel):
        print('GetRoundCount')
        return self.games[channel.id].roundCount
    
    @classmethod
    async def TryClearIsNewRound(self, channel:discord.TextChannel):
        print('TryClearIsNewRound')
        try:
            game = self.games[channel.id]
        except:
            await channel.send("Something went wrong with the game mode.")
            return False
        game.isNewRound = False
        return True

    @classmethod
    async def TryJoinPlayer(self, channel:discord.TextChannel, player:discord.User):
        print('TryJoinPlayer')
        try:
            game = self.games[channel.id]
        except:
            return ToDJoinResponse.GameNotExist
        
        if player in game.players:
            return ToDJoinResponse.AlreadyPlaying
        
        if game.state == GameState.NOT_STARTED or game.state == GameState.GAME_ENDING:
            return ToDJoinResponse.GameNotExist

        try:
            game.players.append(player)
            if game.game_mode == GameMode.GameMode_Chaos or game.game_mode == GameMode.GameMode_TrueChaos:
                game.selection_list.append(player)
                print (f"{player} joined.")
        except:
            #cleanup, make sure they were never added
            try:
                game.players.remove(player)
                try:
                    game.selection_list.remove(player)
                except:
                    pass
            except:
                return ToDJoinResponse.Error
            return ToDJoinResponse.Error    #something went wrong, do not join the player
        return ToDJoinResponse.SuccessfulJoin

    @classmethod
    async def TryLeavePlayer(self, channel:discord.TextChannel, player:discord.User):
        print('TryLeavePlayer')
        try:
            game = self.games[channel.id]
        except:
            return ToDLeaveResponse.GameNotExist

        if player in game.players:
            try:
                game.players.remove(player)
                try:    
                    game.selection_list.remove(player)
                except:
                    pass
            except:
                return ToDLeaveResponse.NotPlaying
        else:
            return ToDLeaveResponse.NotPlaying
        return ToDLeaveResponse.SuccessfulLeave

    @classmethod
    async def TryClearWasSkipped(self, channel:discord.TextChannel):
        print('TryClearWasSkipped')
        try:
            game = self.games[channel.id]
        except:
            await channel.send("Something went wrong with the game mode.")
            return False
        game.wasSkipped = False

    @classmethod
    async def TryNextGameMode(self, channel:discord.TextChannel, player:discord.User):
        print('TryNextGameMode')
        try:
            game = self.games[channel.id]
        except:
            await channel.send("Something went wrong with the game mode.")
            return False
        
        if (player != game.creator):
            return False
            
        nextVal = game.game_mode.value + 1
        if nextVal >= 4:
            nextVal -= 3
        game.game_mode = GameMode(nextVal)
        return True
    
    @classmethod
    async def TrySetToDChoice(self, channel:discord.TextChannel, player:discord.User, todChoice:ToDChoice):
        print('TrySetToDChoice')
        try:
            self.games[channel.id].current_choice = todChoice
        except:
            return False
        return True
    
    @classmethod
    async def TrySetGameState(self, channel:discord.TextChannel, state:GameState):
        print('TrySetGameState')
        try:
            self.games[channel.id].state = state
        except:
            await channel.send("Something went wrong changing the game state.")
            return False
        if state == GameState.NOT_STARTED:
            del self.games[channel.id]
        else:
            await self.games[channel.id].OnStateChange()
        return True

    @classmethod
    async def TryPass(self, channel:discord.TextChannel):
        print('TryPass')
        try:
            game = self.games[channel.id]
        except:
            await channel.send("Something went wrong with the game.")
            return False
        
        game.recentOutcome = True

        await self.TrySetGameState(channel, GameState.INPUT_COMPLETE)
        return True
      
    @classmethod
    async def TryFail(self, channel:discord.TextChannel):
        print('TryFail')
        try:
            game = self.games[channel.id]
        except:
            await channel.send("Something went wrong with the game.")
            return False
        
        game.recentOutcome = False
        await self.TrySetGameState(channel, GameState.INPUT_COMPLETE)
        return True

    @classmethod
    async def TryEndGame(self, channel:discord.TextChannel):
        print('TryEndGame')
        await self.games[channel.id].EndGame()
        time.sleep(1)
        try:
            del self.games[channel.id]
        except:
            return False
        return True
    
    @classmethod
    async def TryToggleSkip(self, channel:discord.TextChannel, user:discord.User):
        print('TryToggleSkip')
        return await self.games[channel.id].ToggleSkip(user)
    
    @classmethod
    async def TryAddToD(self, channel:discord.TextChannel, message:discord.Message):
        print('TryAddToD')
        if self.games[channel.id].game_mode == GameMode.GameMode_TrueChaos:
            self.games[channel.id].ToDOptions.append(ToDOption(message.author.id, message.content))
            return True
        #picking is handled on embed timeout
        else:
            if message.author.id == self.games[channel.id].current_chooser.id:
                self.games[channel.id].ToDOptions.append(ToDOption(message.author.id, message.content))
                self.games[channel.id].state = GameState.INPUT_GIVEN
                await self.games[channel.id].OnStateChange()
                return True

    @classmethod
    async def TryAddToD(self, channel:discord.TextChannel, message:str, user:discord.User):
        print('TryAddToD')
        if self.games[channel.id].game_mode == GameMode.GameMode_TrueChaos:
            self.games[channel.id].ToDOptions.append(ToDOption(user.id, message))
            return True
            #picking is handled on embed timeout
        else:
            if user.id == self.games[channel.id].current_chooser.id:
                self.games[channel.id].ToDOptions.append(ToDOption(user.id, message))
                self.games[channel.id].state = GameState.INPUT_GIVEN
                await self.games[channel.id].OnStateChange()
                return True
            else:
                return False

    @classmethod
    async def EvaluateGameEnd(self, channel:discord.TextChannel):
        print('EvaluateGameEnd')
        return await self.games[channel.id].EvaluateGameEnd()

    @classmethod
    async def ProcessSkipState(self, channel:discord.TextChannel):
        print('ProcessSkipState')
        try:
            await self.games[channel.id].CheckSkip()
        except Exception:
            return False

    @classmethod
    async def ProcessTruthDareText(self, message:discord.Message):
        print('ProcessTruthDareText')
        messageText = message.content[6:] if (message.content[0:5].lower() == "truth") else message.content[5:]
        messageText = messageText[1:] if messageText[0] == ' ' else messageText

        await self.TryAddToD(message.channel, messageText, message.author)
 
    @classmethod
    async def RefreshView(self, channel:discord.TextChannel, timeOut:int = None):
        print('RefreshView')
        try:
            await self.games[channel.id].gameView.RefreshView(timeOut)
        except:
            return None

    @classmethod
    async def ResetGames(self):
        print('ResetGames')
        self.games.clear()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        ctx = await self.bot.get_context(message)
        if ctx.invoked_subcommand is not None:
            return
        
        try:
            curGame = self.games[message.channel.id]
        except:
            return
        if curGame.state != GameState.PLAYER_HAS_CHOSEN_AWAITING_INPUT:
            if (message.content.lower() == ";tod reset"):
                await self.ResetGames()
            return False
        if len(message.content) < 5:
            return False
        if (message.content[0:6].lower() == "truth:" and curGame.current_choice == ToDChoice.Truth) or (message.content[0:5].lower() == "dare:" and curGame.current_choice == ToDChoice.Dare):
            await self.ProcessTruthDareText(message)
            return True
    
    @commands.group(name="tod", autohelp=False)
    async def tod(self, ctx):
        print('tod')

        if ctx.invoked_subcommand is not None:
            return
        if self.games.get(ctx.channel.id) is not None:
            await ctx.send("ToD game already running in this channel!")
            return
        
        newGame = ToDGame(ctx.channel, ctx.author)
        self.games[ctx.channel.id] = newGame
        self.games[ctx.channel.id].state = GameState.GAME_STARTING
        await self.TryJoinPlayer(ctx.channel, ctx.author)
        await self.games[ctx.channel.id].SpawnView(30)

    @commands.admin_or_permissions(manage_guild=True)
    @tod.command(name="clear", autohelp=False)
    async def todclear(self, ctx):
        print('todclear')
        await self.ResetGames()
        await ctx.send("Reset ToD games!")