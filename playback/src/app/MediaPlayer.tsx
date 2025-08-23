'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';

interface VTTCue {
  start: number;
  end: number;
  url: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface MediaPlayerProps {
  src: string;
}

const MediaPlayer: React.FC<MediaPlayerProps> = ({ src }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(60);
  const [volume, setVolume] = useState(1);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [cues, setCues] = useState<VTTCue[]>([]);
  const [isHoveringScrubBar, setIsHoveringScrubBar] = useState(false);
  const [previewFrame, setPreviewFrame] = useState<VTTCue | null>(null);
  const [previewPosition, setPreviewPosition] = useState(0);
  const [hoverTime, setHoverTime] = useState(0);
  const [hoverProgress, setHoverProgress] = useState(0);
  const [isHoveringPlayer, setIsHoveringPlayer] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const scrubBarRef = useRef<HTMLDivElement>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);

  // Parse VTT file to get sprite cues
  const parseVTT = useCallback(async () => {
    try {
      const response = await fetch('/thumbnails.vtt');
      const vttText = await response.text();
      const lines = vttText.split(/\r?\n/);
      const parsedCues: VTTCue[] = [];

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.includes('-->')) {
          const [startStr, endStr] = line.split('-->').map(s => s.trim());
          
          let j = i + 1;
          while (j < lines.length && !lines[j].trim()) j++;
          
          if (j >= lines.length) break;
          
          const target = lines[j].trim();
          const m = target.match(/^(.*)#xywh=(\d+),(\d+),(\d+),(\d+)$/);
          
          if (!m) continue;
          
          const [_, url, x, y, w, h] = m;
          
          parsedCues.push({
            start: toSeconds(startStr),
            end: toSeconds(endStr),
            url, 
            x: parseInt(x), 
            y: parseInt(y), 
            w: parseInt(w), 
            h: parseInt(h)
          });
          
          i = j;
        }
      }
      
      return parsedCues;
    } catch (error) {
      console.error('Error parsing VTT:', error);
      return [];
    }
  }, []);

  // Convert time string to seconds (HH:MM:SS.mmm)
  const toSeconds = (hms: string): number => {
    const [hh, mm, ss] = hms.split(':').map(parseFloat);
    return hh * 3600 + mm * 60 + ss;
  };

  // Fetch and parse VTT file on mount
  useEffect(() => {
    parseVTT().then(setCues);
  }, [parseVTT]);

  // Hover play/pause effect
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    if (isHoveringPlayer) {
      videoElement.play().catch(error => {
        console.error('Error playing video:', error);
      });
    } else {
      videoElement.pause();
    }
  }, [isHoveringPlayer]);

  // Video event handlers
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    const handleLoadedMetadata = () => {
      setDuration(videoElement.duration);
    };

    const handleTimeUpdate = () => {
      if (!isScrubbing) {
        setCurrentTime(videoElement.currentTime);
      }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    videoElement.addEventListener('loadedmetadata', handleLoadedMetadata);
    videoElement.addEventListener('timeupdate', handleTimeUpdate);
    videoElement.addEventListener('play', handlePlay);
    videoElement.addEventListener('pause', handlePause);

    return () => {
      videoElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
      videoElement.removeEventListener('timeupdate', handleTimeUpdate);
      videoElement.removeEventListener('play', handlePlay);
      videoElement.removeEventListener('pause', handlePause);
    };
  }, [isScrubbing]);

  // Scrub bar hover preview
  const handleScrubBarMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (cues.length === 0) return;

    const { left, width } = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - left;
    const progress = mouseX / width;
    const hoverTime = progress * duration;

    // Find and set preview frame for current mouse position
    const currentCue = cues.find(cue => 
      hoverTime >= cue.start && hoverTime < cue.end
    );
    
    if (currentCue) {
      setPreviewFrame(currentCue);
      setPreviewPosition(mouseX);
      setIsHoveringScrubBar(true);
      setHoverTime(hoverTime);
      setHoverProgress(progress);
    }
  };

  // Handle scrub bar hover state
  const handleScrubBarMouseLeave = () => {
    setIsHoveringScrubBar(false);
    setPreviewFrame(null);
    setHoverProgress(0);
  };

  // Format time to MM:SS
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  // Scrub bar interaction
  const handleScrubBarMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    setIsScrubbing(true);
    videoElement.pause();

    const updateTime = (clientX: number) => {
      const scrubBar = scrubBarRef.current;
      if (!scrubBar) return;

      const rect = scrubBar.getBoundingClientRect();
      const percent = (clientX - rect.left) / rect.width;
      const newTime = percent * duration;

      videoElement.currentTime = Math.min(Math.max(0, newTime), duration);
      setCurrentTime(videoElement.currentTime);
    };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      updateTime(moveEvent.clientX);
    };

    const handleMouseUp = () => {
      setIsScrubbing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);

      // Automatically play if the player is being hovered
      if (isHoveringPlayer) {
        videoElement.play().catch(error => {
          console.error('Error playing video after scrubbing:', error);
        });
      }
    };

    updateTime(e.clientX);

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  // Volume control
  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    const videoElement = videoRef.current;
    
    if (videoElement) {
      videoElement.volume = newVolume;
      setVolume(newVolume);
    }
  };

  return (
    <div 
      ref={playerContainerRef}
      className="w-full max-w-2xl mx-auto bg-black rounded-lg overflow-hidden shadow-lg"
      onMouseEnter={() => setIsHoveringPlayer(true)}
      onMouseLeave={() => setIsHoveringPlayer(false)}
    >
      {/* Video Container */}
      <div className="relative w-full aspect-video">
        {/* Thumbnail */}
        {!isPlaying && (
          <img 
            src="/thumbnail.jpg" 
            alt="Video Thumbnail" 
            className="absolute inset-0 w-full h-full object-cover z-10"
          />
        )}

        <video
          ref={videoRef}
          src={src}
          muted
          className="w-full h-full object-contain"
        />
      </div>

      {/* Controls */}
      <div className="bg-gray-800 p-4">
        {/* Scrub Bar */}
        <div
          ref={scrubBarRef}
          className="relative w-full h-2 bg-gray-700 rounded-full cursor-pointer mb-2"
          onMouseMove={handleScrubBarMouseMove}
          onMouseLeave={handleScrubBarMouseLeave}
          onMouseDown={handleScrubBarMouseDown}
        >
          {/* Sprite Preview */}
          {isHoveringScrubBar && previewFrame && (
            <>
              <div
                className="absolute bottom-full left-0 z-10"
                style={{
                  left: `${previewPosition - 50}px`, // Center the preview
                  width: '100px',
                  height: '56px',
                  border: '1px solid white',
                  backgroundColor: 'black',
                  backgroundImage: `url(/${previewFrame.url})`,
                  backgroundPosition: `-${previewFrame.x}px -${previewFrame.y}px`,
                  backgroundRepeat: 'no-repeat'
                }}
              />
              <div
                className="absolute bottom-full left-0 z-10 text-white text-xs text-center w-[100px]"
                style={{
                  left: `${previewPosition - 50}px`, // Center the time label
                  top: 'calc(100% + 2px)'
                }}
              >
                {formatTime(hoverTime)}
              </div>
            </>
          )}

          {/* Hover Progress Bar - Now rendered BEFORE the red progress bar */}
          {isHoveringScrubBar && (
            <div
              className="absolute top-0 left-0 h-full bg-gray-500 rounded-full"
              style={{
                width: `${hoverProgress * 100}%`,
                zIndex: 1 // Ensure it's under the red bar
              }}
            />
          )}

          {/* Progress Bar */}
          <div
            className="absolute top-0 left-0 h-full bg-red-600 rounded-full"
            style={{
              width: `${(currentTime / duration) * 100}%`,
              zIndex: 2 // Ensure it's on top of the grey bar
            }}
          />
        </div>

        {/* Control Bar */}
        <div className="flex items-center space-x-4">
          {/* Time Display */}
          <div className="text-white text-sm">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          {/* Volume Control */}
          <div className="flex items-center space-x-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1" 
              value={volume}
              onChange={handleVolumeChange}
              className="w-24 h-1 bg-gray-700 rounded-full appearance-none"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MediaPlayer;
