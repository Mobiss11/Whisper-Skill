import unittest
from unittest import mock

from scripts.audio_ducking import WindowsAudioDucker, clamp_reduction_percent


class FakeVolume:
    def __init__(self, value):
        self.value = float(value)
        self.writes = []

    def GetMasterVolume(self):
        return self.value

    def SetMasterVolume(self, value, _context):
        self.value = float(value)
        self.writes.append(self.value)


class FakeSession:
    def __init__(self, pid, value):
        self.ProcessId = pid
        self.SimpleAudioVolume = FakeVolume(value)


class AudioDuckingTests(unittest.TestCase):
    def test_percent_is_clamped(self):
        self.assertEqual(clamp_reduction_percent(-5), 0)
        self.assertEqual(clamp_reduction_percent(72.6), 73)
        self.assertEqual(clamp_reduction_percent(100), 90)
        self.assertEqual(clamp_reduction_percent("bad"), 70)

    @mock.patch("scripts.audio_ducking.platform.system", return_value="Windows")
    def test_ducks_other_sessions_and_restores_exact_volume(self, _system):
        own = FakeSession(10, 0.8)
        music = FakeSession(20, 0.8)
        ducker = WindowsAudioDucker(
            enabled=True,
            reduction_percent=75,
            session_provider=lambda: [own, music],
            process_id=10,
        )

        self.assertEqual(ducker.duck(), 1)
        self.assertAlmostEqual(own.SimpleAudioVolume.value, 0.8)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, 0.2)
        self.assertTrue(ducker.active)

        self.assertEqual(ducker.restore(), 1)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, 0.8)
        self.assertFalse(ducker.active)

    @mock.patch("scripts.audio_ducking.platform.system", return_value="Windows")
    def test_preserves_manual_change_made_while_recording(self, _system):
        music = FakeSession(20, 0.8)
        ducker = WindowsAudioDucker(
            enabled=True,
            reduction_percent=50,
            session_provider=lambda: [music],
            process_id=10,
        )

        ducker.duck()
        music.SimpleAudioVolume.value = 0.3
        ducker.restore()
        self.assertAlmostEqual(music.SimpleAudioVolume.value, 0.6)

    @mock.patch("scripts.audio_ducking.platform.system", return_value="Windows")
    def test_disabled_mode_does_nothing(self, _system):
        music = FakeSession(20, 0.8)
        ducker = WindowsAudioDucker(
            enabled=False,
            reduction_percent=70,
            session_provider=lambda: [music],
        )

        self.assertEqual(ducker.duck(), 0)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, 0.8)


if __name__ == "__main__":
    unittest.main()
