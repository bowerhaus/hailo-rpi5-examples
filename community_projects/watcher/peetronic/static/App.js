new Vue({
    el: '#app',
    data: {
        files: [],
        selectedFile: null,
        error: null,
        loading: true,
        player: null
    },
    created() {
        this.fetchFiles();
    },
    methods: {
        fetchFiles() {
            this.loading = true;
            this.error = null;
            axios.get('/api/files')
                .then(response => {
                    this.files = response.data;
                })
                .catch(error => {
                    this.error = 'Failed to load files';
                })
                .finally(() => {
                    this.loading = false;
                });
        },
        selectFile(file) {
            // Clean up existing video player
            if (this.player) {
                this.player.dispose();
                this.player = null;
                // Remove the video element completely
                const oldPlayer = document.getElementById('video-player');
                if (oldPlayer) {
                    oldPlayer.parentNode.removeChild(oldPlayer);
                }
            }
            
            this.selectedFile = file;
            
            // Create new video player if needed
            if (this.selectedFile && this.selectedFile.endsWith('.mp4')) {
                this.$nextTick(() => {
                    const videoElement = document.createElement('video');
                    videoElement.id = 'video-player';
                    videoElement.className = 'video-js vjs-default-skin';
                    document.querySelector('#media-container').appendChild(videoElement);
                    
                    this.player = videojs('video-player', {
                        controls: true,
                        preload: 'auto',
                        width: 960,
                        height: 400,
                        autoplay: true,
                        sources: [{
                            src: '/media/' + this.selectedFile,
                            type: 'video/mp4'
                        }]
                    });
                });
            }

            if (this.selectedFile && this.selectedFile.endsWith('.mkv')) {
                this.$nextTick(() => {
                    const videoElement = document.createElement('video');
                    videoElement.id = 'video-player';
                    videoElement.className = 'video-js vjs-default-skin';
                    document.querySelector('#media-container').appendChild(videoElement);
                    
                    this.player = videojs('video-player', {
                        controls: true,
                        preload: 'auto',
                        width: 600,
                        height: 337,
                        autoplay: true,
                        sources: [{
                            src: '/media/' + this.selectedFile,
                            type: 'video/x-matroska'
                        }]
                    });
                });
            }
        }
    },
    beforeDestroy() {
        if (this.player) {
            this.player.dispose();
        }
    },
    template: `
        <div>
            <h1>Available Media Files</h1>
            <div v-if="loading">Loading...</div>
            <div v-else-if="error">{{ error }}</div>
            <div v-else-if="files.length === 0">No media files found</div>
            <ul v-else>
                <li v-for="file in files" :key="file">
                    <a href="#" @click.prevent="selectFile(file)">{{ file }}</a>
                </li>
            </ul>
            <div id="media-container" v-if="selectedFile">
                <img v-if="selectedFile.endsWith('.jpg')" :src="'/media/' + selectedFile" width="600" />
            </div>
        </div>
    `
});
