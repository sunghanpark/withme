import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtubesearchpython import VideosSearch
from concurrent.futures import ThreadPoolExecutor

def initialize_session_state():
    """세션 상태 초기화"""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'is_searching' not in st.session_state:
        st.session_state.is_searching = False
    if 'stop_search' not in st.session_state:
        st.session_state.stop_search = False
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""
    if 'searched_videos' not in st.session_state:
        st.session_state.searched_videos = set()
    if 'search_input' not in st.session_state:
        st.session_state.search_input = ""

def perform_search():
    """검색 실행 함수"""
    if 'search_input' not in st.session_state:
        return False
        
    if st.session_state.search_input and not st.session_state.is_searching:
        st.session_state.search_query = st.session_state.search_input
        st.session_state.is_searching = True
        st.session_state.stop_search = False
        st.session_state.searched_videos = set()
        return True
    return False

class YouTubeSubtitleSearch:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=3)

    def find_additional_usage_examples(self, subtitles, search_query, current_idx, count=2):
        """주어진 검색어의 추가 사용 예시를 찾는 함수"""
        examples = []
        search_query_lower = search_query.lower()
        
        for idx, subtitle in enumerate(subtitles):
            if idx == current_idx:
                continue
                
            if not subtitle or 'text' not in subtitle:
                continue
                
            if search_query_lower in subtitle['text'].lower():
                full_sentence = self.get_full_sentence(subtitles, idx)
                if full_sentence and full_sentence not in examples:
                    timestamp = int(subtitle.get('start', 0))
                    minutes = timestamp // 60
                    seconds = timestamp % 60
                    examples.append({
                        'sentence': full_sentence,
                        'timestamp': f"{minutes}:{seconds:02d}",
                        'start_time': timestamp
                    })
                    
                    if len(examples) >= count:
                        break
        
        return examples

    def get_full_sentence(self, subtitles, current_index):
        if not subtitles or current_index >= len(subtitles):
            return ""
            
        sentence = subtitles[current_index]['text']
        
        if not sentence.strip().endswith('.'):
            i = current_index + 1
            while i < len(subtitles):
                next_text = subtitles[i]['text']
                sentence += ' ' + next_text
                if next_text.strip().endswith('.'):
                    break
                i += 1
        
        if not sentence[0].isupper() and current_index > 0:
            i = current_index - 1
            while i >= 0:
                prev_text = subtitles[i]['text']
                if prev_text.strip().endswith('.'):
                    break
                sentence = prev_text + ' ' + sentence
                i -= 1
        
        return sentence.strip()

    def search_videos(self, search_query):
        try:
            videosSearch = VideosSearch(search_query, limit=50)
            results = videosSearch.result()
            
            if not results or 'result' not in results:
                return []
                
            videos = []
            for result in results['result']:
                if not result or 'id' not in result:
                    continue
                
                video = {
                    'id': result['id'],
                    'title': result.get('title', 'No Title'),
                    'url': result.get('link', ''),
                    'thumbnail': result.get('thumbnails', [{'url': ''}])[0].get('url', ''),
                    'duration': result.get('duration', ''),
                    'viewCount': result.get('viewCount', {}).get('text', ''),
                    'publishedTime': result.get('publishedTime', '')
                }
                videos.append(video)
            
            return videos
        except Exception as e:
            st.error(f"검색 오류: {str(e)}")
            return []

    def get_video_subtitles(self, video):
        if not video or not video.get('id'):
            return None, None, None, None
            
        try:
            url = video.get('url', '')
            thumbnail = video.get('thumbnail', '')
            transcript = None
            
            languages = ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
            for lang in languages:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video['id'], languages=[lang])
                    if transcript:
                        break
                except:
                    continue
            
            return transcript, video.get('title'), url, thumbnail
        except Exception as e:
            return None, None, None, None

def main():
    # 가장 먼저 세션 상태 초기화
    initialize_session_state()
    
    st.set_page_config(
        page_title="영어 수업을 위한 유튜브 자막 검색",
        page_icon="🎥",
        layout="wide"
    )

    st.title("영어 수업을 위한 유튜브 자막 검색 🎥")
    
    searcher = YouTubeSubtitleSearch()
    
    # 검색 인터페이스
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        search_text = st.text_input(
            "검색어를 입력하세요", 
            key="search_input",
            value=st.session_state.search_query,
            on_change=perform_search
        )
    with col2:
        search_button = st.button(
            "검색", 
            type="primary", 
            use_container_width=True,
            disabled=st.session_state.is_searching,
            on_click=perform_search
        )
    
    with col3:
        stop_button = st.button(
            "중단",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.is_searching,
            on_click=lambda: setattr(st.session_state, 'stop_search', True)
        )
    
    if st.session_state.is_searching:
        with st.spinner("검색 중..."):
            videos = searcher.search_videos(st.session_state.search_query)
            
            if not videos:
                st.warning("검색 결과를 찾을 수 없습니다. 다른 검색어를 시도해보세요.")
                st.session_state.is_searching = False
                return
            
            video_count = 0
            results = []
            
            progress_container = st.container()
            with progress_container:
                progress_bar = st.progress(0)
                progress_text = st.empty()
                status_text = st.empty()
            
            total_videos = len(videos)
            
            for i, video in enumerate(videos):
                if st.session_state.stop_search:
                    st.warning("검색이 중단되었습니다.")
                    break
                
                if not video or not video.get('id'):
                    continue
                
                # 이미 검색한 비디오 스킵
                if video['id'] in st.session_state.searched_videos:
                    continue
                
                progress = int((i + 1) / total_videos * 100)
                progress_bar.progress(progress / 100)
                progress_text.markdown(f"### 진행률: {progress}%")
                
                subtitles, title, url, thumbnail = searcher.get_video_subtitles(video)
                st.session_state.searched_videos.add(video['id'])
                
                if subtitles:
                    for idx, subtitle in enumerate(subtitles):
                        if st.session_state.stop_search:
                            break
                        
                        if not subtitle or 'text' not in subtitle:
                            continue
                            
                        if st.session_state.search_query.lower() in subtitle['text'].lower():
                            full_sentence = searcher.get_full_sentence(subtitles, idx)
                            if not full_sentence:
                                continue
                            
                            additional_examples = searcher.find_additional_usage_examples(
                                subtitles, 
                                st.session_state.search_query, 
                                idx
                            )
                            
                            timestamp = int(subtitle.get('start', 0))
                            minutes = timestamp // 60
                            seconds = timestamp % 60
                            
                            results.append({
                                'title': title or 'No Title',
                                'full_sentence': full_sentence,
                                'timestamp': f"{minutes}:{seconds:02d}",
                                'url': url or '#',
                                'start_time': timestamp,
                                'thumbnail': thumbnail or '',
                                'duration': video.get('duration', ''),
                                'viewCount': video.get('viewCount', ''),
                                'publishedTime': video.get('publishedTime', ''),
                                'additional_examples': additional_examples
                            })
                            video_count += 1
                            status_text.text(f"검색된 동영상: {video_count}개")
                            break
            
            st.session_state.search_results = results
            progress_container.empty()
            
            if len(results) == 0:
                st.info("자막에서 검색어를 찾을 수 없습니다. 다른 검색어나 표현을 시도해보세요.")
            elif st.session_state.stop_search:
                st.warning(f"검색이 중단됨 - 찾은 동영상: {video_count}개")
            else:
                st.success(f"검색 완료 - 찾은 동영상: {video_count}개")
            
            st.session_state.is_searching = False
            st.session_state.stop_search = False
    
    if st.session_state.search_results:
        for result in st.session_state.search_results:
            with st.container():
                col1, col2 = st.columns([1, 3])
                with col1:
                    if result.get('thumbnail'):
                        st.image(result['thumbnail'], use_column_width=True)
                with col2:
                    st.markdown(f"### {result['title']}")
                    duration_info = f"⏱️ {result.get('duration', '')} | " if result.get('duration') else ""
                    views_info = f"👀 {result.get('viewCount', '')} | " if result.get('viewCount') else ""
                    published_info = f"📅 {result.get('publishedTime', '')}" if result.get('publishedTime') else ""
                    st.markdown(f"{duration_info}{views_info}{published_info}")
                    
                    # 메인 사용 예시
                    st.markdown("#### Example 1:")
                    st.markdown(f"**▶ {result['timestamp']}**")
                    st.text(result['full_sentence'])
                    
                    # 추가 사용 예시들
                    for i, example in enumerate(result.get('additional_examples', []), 2):
                        st.markdown(f"#### Example {i}:")
                        st.markdown(f"**▶ {example['timestamp']}**")
                        st.text(example['sentence'])
                    
                    if result.get('url') and result.get('start_time'):
                        url_with_timestamp = f"{result['url']}&t={result['start_time']}"
                        st.markdown(f"[동영상 보기]({url_with_timestamp})")
                        
                        # 추가 예시들에 대한 타임스탬프 링크
                        for i, example in enumerate(result.get('additional_examples', []), 2):
                            url_with_timestamp = f"{result['url']}&t={example['start_time']}"
                            st.markdown(f"[Example {i} 보기]({url_with_timestamp})")
                            
                st.divider()

if __name__ == "__main__":
    main()