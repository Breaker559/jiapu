import { Play } from 'lucide-react';
import type { Entry } from './types';

export const isVideo=(media:Entry)=>media.data.media_type==='video';
export function mediaDuration(seconds:number=0){const value=Math.floor(seconds);return `${Math.floor(value/60)}:${String(value%60).padStart(2,'0')}`;}
export default function MediaThumbnail({media,fid}:{media:Entry;fid:string}) {
 return <span className="media-thumbnail"><img loading="lazy" alt={media.data.title||'家族记忆'} src={`/api/families/${fid}/media/${media.id}/thumb?v=${media.version}`}/>{isVideo(media)&&<><span className="media-play"><Play size={22} fill="currentColor"/></span><small className="media-duration">视频 · {mediaDuration(media.data.duration)}</small></>}</span>;
}
