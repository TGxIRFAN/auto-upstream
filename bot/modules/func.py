#!/usr/bin/env python3
from re import findall as refindall
from subprocess import run as srun, check_output as scheck_output
from os import remove as osremove, rename as osrename, path as ospath

from bot import LOGGER, user_data

async def change_metadata(file, dirpath, key):
    LOGGER.info(f"Trying to change metadata for file: {file}")
    temp_file = f"{file}.temp.mkv"
    
    full_file_path = os.path.join(dirpath, file)
    temp_file_path = os.path.join(dirpath, temp_file)
    
    cmd = ['ffprobe', '-hide_banner', '-loglevel', 'error', '-print_format', 'json', '-show_streams', full_file_path]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        LOGGER.error(f"Error getting stream info: {stderr.decode().strip()}")
        return file
    
    streams = json.loads(stdout)['streams']
    
    cmd = ['ffmpeg', '-y', '-i', full_file_path, '-c', 'copy', '-metadata', f'title={key}']
    
    audio_index = 0
    subtitle_index = 0
    
    for stream in streams:
        stream_index = stream['index']
        stream_type = stream['codec_type']
        
        cmd.extend(['-map', f'0:{stream_index}'])
        
        if stream_type == 'video':
            cmd.extend([f'-metadata:s:v:{stream_index}', f'title={key}'])
        elif stream_type == 'audio':
            cmd.extend([f'-metadata:s:a:{audio_index}', f'title={key}'])
            audio_index += 1
        elif stream_type == 'subtitle':
            cmd.extend([f'-metadata:s:s:{subtitle_index}', f'title={key}'])
            subtitle_index += 1
    
    cmd.append(temp_file_path)
    
    process = await create_subprocess_exec(*cmd, stderr=PIPE)
    await process.wait()
    
    if process.returncode != 0:
        LOGGER.error(f"Error changing metadata for file: {file}")
        return file
    
    os.replace(temp_file_path, full_file_path)
    LOGGER.info(f"Metadata changed successfully for file: {file}")
    return file
    
async def edit_video_titles(user_id, file_path):
    if not file_path.lower().endswith(('.mp4', '.mkv')):
        return
    user_dict = user_data.get(user_id, {})
    if user_dict.get("metadata", False):
        new_title = user_dict["metadata"]
        directory = ospath.dirname(file_path)
        file_name = ospath.basename(file_path)
        file_name_cleaned = re.sub(r'www\S+', '', file_name)
        file_name_cleaned = re.sub(r'[_\-]+', ' ', file_name_cleaned).strip()
        title_metadata = f'{metadata} - {file_name_cleaned}'.strip()
        new_file = ospath.join(directory, f"new_{file_name}")
        LOGGER.info(f"Editing videos metadata title")
        command_probe = ["ffprobe", "-v", "error", "-show_entries", "stream=index", "-select_streams", "a", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        try:
            probe_result = scheck_output(command_probe).decode("utf-8").strip()
            audio_stream_count = len(refindall(r'\d+', probe_result))
        except:
            audio_stream_count = 0
        
        command_probe_subtitles = ["ffprobe", "-v", "error", "-show_entries", "stream=index", "-select_streams", "s", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        try:
            probe_result_subtitles = scheck_output(command_probe_subtitles).decode("utf-8").strip()
            subtitle_stream_count = len(refindall(r'\d+', probe_result_subtitles))
        except:
            subtitle_stream_count = 0

        cmd = ["ffmpeg", "-i", file_path, "-map", "0", "-c", "copy"]
        cmd += ["-metadata:s:v:0", f"title={title_metadata}"]
        for i in range(audio_stream_count):
            cmd += ["-metadata:s:a:{}".format(i), f"title={title_metadata}"]
        for i in range(subtitle_stream_count):
            cmd += ["-metadata:s:s:{}".format(i), f"title={title_metadata}"]

        cmd += ["-metadata", f"title={title_metadata}"]
        cmd.append(new_file)
        srun(cmd, check=True)
        osremove(file_path)
        osrename(new_file, f"{directory}/{file_name}")
