import MediaPlayer from './MediaPlayer';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-black">
      <h1 className="text-2xl mb-8 text-white">YouTube-Like Video Player</h1>
      <MediaPlayer src="/mov_bbb.mp4" />
    </main>
  )
}