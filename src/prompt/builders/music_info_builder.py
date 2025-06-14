import subprocess


class MusicInfoBuilder:
    """
    Extracts current Apple Music playback info (title, artist, genre)
    """
    def get_music_info_prompt(self) -> str:
        script = '''
        tell application "Music"
            if it is running and player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                set genreName to genre of current track
                return trackName & "||" & artistName & "||" & genreName
            else
                return ""
            end if
        end tell
        '''
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            output = result.stdout.strip()

            if not output or "||" not in output:
                return ""

            title, artist, genre = output.split("||")
            return (f"The song currently playing is <{title}>, by {artist}, and belongs to {genre}. "
                    f"If someone asks you about current playing music, you can answer and start some music topics."
                    f" If no one asks, you don't need to actively talk about it. "
                    f"You like Jazz Music, but your creator Whisper(boy not girl) likes Rock & Roll.")
        except Exception:
            return ""


if __name__ == '__main__':
    music_builder = MusicInfoBuilder()
    print(music_builder.get_music_info_prompt())