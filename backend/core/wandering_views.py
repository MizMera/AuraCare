from pathlib import Path

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import parsers, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import CustomUser
from .wandering_pipeline import get_artifacts, get_status, get_video_artifact_path, launch_pipeline, stop_pipeline


def _wandering_access_allowed(user):
    return user.role in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]


class QueryStringJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth

        raw_token = request.query_params.get('token')
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


def _stream_file(file_path: Path, start: int, end: int, chunk_size: int = 8192):
    with file_path.open('rb') as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            chunk = handle.read(read_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


class WanderingPipelineLaunchView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can launch the wandering pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        input_mode = str(request.data.get('input_mode', 'webcam')).strip().lower()
        duration_seconds = int(request.data.get('duration_seconds', 20) or 20)
        video_input_path = request.data.get('video_input_path')
        webcam_index = int(request.data.get('webcam_index', 0) or 0)

        try:
            payload = launch_pipeline(
                requested_by=request.user.username,
                input_mode=input_mode,
                video_input_path=video_input_path,
                webcam_index=webcam_index,
                duration_seconds=duration_seconds,
            )
        except FileNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'error': f'Unable to launch wandering pipeline: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(payload, status=status.HTTP_202_ACCEPTED if payload.get('running') else status.HTTP_200_OK)


class WanderingPipelineUploadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]

    def post(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can upload videos for the wandering pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        blob = request.FILES.get('video_file') or request.FILES.get('blob')
        if blob is None:
            return Response({'error': 'No video file was uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        upload_dir = Path(settings.MEDIA_ROOT) / 'uploads' / 'wandering'
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f'{timestamp}_{Path(blob.name).name}'
        video_path = upload_dir / safe_name

        with video_path.open('wb') as handle:
            for chunk in blob.chunks():
                handle.write(chunk)

        try:
            payload = launch_pipeline(
                requested_by=request.user.username,
                input_mode='upload',
                video_input_path=str(video_path),
            )
        except Exception as exc:
            return Response({'error': f'Unable to start wandering analysis: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                'ok': True,
                'filename': blob.name,
                'video_path': str(video_path),
                'status': payload,
            },
            status=status.HTTP_201_CREATED,
        )


class WanderingPipelineStatusView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can view wandering pipeline status.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(get_status(), status=status.HTTP_200_OK)


class WanderingPipelineArtifactsView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can view wandering artifacts.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(get_artifacts(), status=status.HTTP_200_OK)


class WanderingPipelineStopView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can stop the wandering pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            payload = stop_pipeline(requested_by=request.user.username)
        except Exception as exc:
            return Response({'error': f'Unable to stop wandering pipeline: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(payload, status=status.HTTP_200_OK)


class WanderingPipelineStreamView(views.APIView):
    authentication_classes = [QueryStringJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _wandering_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can stream the wandering video.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        video_path = get_video_artifact_path()
        if video_path is None:
            return Response(
                {'error': 'Video file not available. The pipeline may not have generated output yet.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            file_size = video_path.stat().st_size
        except OSError:
            return Response({'error': 'Cannot access video file.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        range_header = request.META.get('HTTP_RANGE', '')
        range_start = 0
        range_end = file_size - 1

        if range_header:
            try:
                range_match = __import__('re').match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    range_start = int(range_match.group(1))
                    if range_match.group(2):
                        range_end = int(range_match.group(2))
            except (ValueError, AttributeError):
                pass

        response = StreamingHttpResponse(
            _stream_file(video_path, range_start, range_end),
            content_type='video/mp4',
            status=206 if range_header else 200,
        )
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = str(range_end - range_start + 1)

        if range_header:
            response['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'

        return response