"""Request validation for trip planning and heatmap."""

import re

from rest_framework import serializers

from trips.domain.sampling import ALLOWED_INTERVALS_MI

_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$", re.IGNORECASE)


def _require_timezone(serializer: serializers.Serializer, value):
    raw = serializer.initial_data.get("departure_time")
    if isinstance(raw, str) and not _TZ_SUFFIX.search(raw.strip()):
        raise serializers.ValidationError(
            "departure_time must include a timezone offset."
        )
    if value.tzinfo is None:
        raise serializers.ValidationError(
            "departure_time must include a timezone offset."
        )
    return value


class PlaceSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90.0, max_value=90.0)
    lon = serializers.FloatField(min_value=-180.0, max_value=180.0)
    label = serializers.CharField(required=False, allow_blank=True, default="")


class PlanTripSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=1.0, max_value=80_000.0)
    checkpoint_interval_mi = serializers.IntegerField(required=False, default=25)

    def validate_departure_time(self, value):
        return _require_timezone(self, value)

    def validate_checkpoint_interval_mi(self, value):
        if value not in ALLOWED_INTERVALS_MI:
            raise serializers.ValidationError(
                "checkpoint_interval_mi must be one of 10, 25, or 50."
            )
        return value

    def validate(self, attrs):
        origin = attrs["origin"]
        destination = attrs["destination"]
        if origin["lat"] == destination["lat"] and origin["lon"] == destination["lon"]:
            raise serializers.ValidationError(
                "origin and destination must be different points."
            )
        return attrs


class LineStringGeometrySerializer(serializers.Serializer):
    type = serializers.CharField()
    coordinates = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(),
            min_length=2,
            max_length=2,
        ),
        min_length=2,
    )

    def validate_type(self, value):
        if value != "LineString":
            raise serializers.ValidationError("geometry.type must be LineString.")
        return value

    def validate_coordinates(self, value):
        for pair in value:
            lon, lat = pair[0], pair[1]
            if not -180.0 <= lon <= 180.0:
                raise serializers.ValidationError(
                    "longitude must be between -180 and 180."
                )
            if not -90.0 <= lat <= 90.0:
                raise serializers.ValidationError(
                    "latitude must be between -90 and 90."
                )
        return value


class HeatmapSerializer(serializers.Serializer):
    """Corridor heatmap from a planned route geometry (PRD §7)."""

    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=1.0, max_value=80_000.0)
    geometry = LineStringGeometrySerializer()

    def validate_departure_time(self, value):
        return _require_timezone(self, value)

