"""Deterministic sleep timing; no wall-clock waits or real Codex sessions."""
import unittest
import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from animation_clock import load_manifest
from family_store import FamilyStore
from leisure import Leisure


class SleepHabitsTests(unittest.TestCase):
    def test_long_work_does_not_spend_the_idle_delay(self):
        rest=Leisure(0,delays=(5,15),snack_chance=0)
        rest.set_busy(True,1)
        rest.tick(10000,True)
        self.assertEqual(rest.phase,'awake')
        self.assertIsNone(rest.deadline)
        rest.set_busy(False,10000)
        rest.tick(10004.99,True)
        self.assertEqual(rest.phase,'awake')
        rest.tick(10005,True)
        self.assertEqual(rest.phase,'entering')

    def test_all_chats_and_children_must_finish(self):
        store=FamilyStore()
        def event(name,session,when,agent=''):
            store.ingest(dict(session_id=session,agent_id=agent,event=name,turn_id='t'),when)
        event('UserPromptSubmit','A',100)
        event('UserPromptSubmit','B',101)
        event('SubagentStart','B',102,'child')
        event('Stop','A',103)
        self.assertTrue(store.pending_work())
        event('Stop','B',104)
        self.assertTrue(store.pending_work())
        event('SubagentStop','B',105,'child')
        self.assertFalse(store.pending_work())

    def test_compaction_and_permission_fallback_are_not_task_completion(self):
        store=FamilyStore()
        for i,event in enumerate(('UserPromptSubmit','PreCompact','PostCompact','SessionStart')):
            store.ingest(dict(session_id='A',event=event,turn_id='t',
                             status='success' if event=='PostCompact' else None),100+i)
        node=store.nodes['A']
        self.assertTrue(node.active)
        self.assertIsNone(node.completion)
        self.assertEqual(node.status,'thinking')
        self.assertTrue(store.pending_work())
        store.ingest(dict(session_id='A',event='PermissionNoDecision',status='idle',turn_id='t'),105)
        self.assertTrue(store.pending_work())
        store.ingest(dict(session_id='A',event='Stop',turn_id='t'),106)
        self.assertFalse(store.pending_work())

    def test_new_work_cancels_the_entire_quiet_period(self):
        rest=Leisure(0,delays=(5,15),snack_chance=0)
        rest.tick(4.9,True)
        self.assertEqual(rest.phase,'awake')
        rest.set_busy(True,4.9)
        rest.set_busy(False,20)
        rest.tick(24.99,True)
        self.assertEqual(rest.phase,'awake')
        rest.tick(25,True)
        self.assertEqual(rest.phase,'entering')
        rest.set_busy(True,25.01)
        self.assertEqual(rest.phase,'awake')

    def test_manual_compaction_without_a_running_task_can_finish(self):
        store=FamilyStore()
        store.ingest(dict(session_id='A',event='PreCompact'),100)
        self.assertTrue(store.pending_work())
        store.ingest(dict(session_id='A',event='PostCompact'),101)
        self.assertFalse(store.pending_work())

    def test_manual_wake_starts_its_own_delay_after_the_animation(self):
        clips=load_manifest(Path(__file__).resolve().parents[1]/'assets/macos-resources')
        rng=Mock()
        rng.random.return_value=.25
        rest=Leisure(0,rng=rng,delays=(5,15))
        rest.enter(0)
        rest.position(clips,7)
        self.assertTrue(rest.click(8,wake=True))
        woke=8+2*clips['left'].total_duration/1000+.01
        rest.position(clips,woke)
        self.assertAlmostEqual(rest.deadline,woke+15)
        rest.tick(woke+14.99,True)
        self.assertEqual(rest.phase,'awake')
        rng.random.assert_not_called()
        rest.tick(woke+15,True)
        self.assertEqual(rest.phase,'snacking')
        rng.random.assert_called_once()

    def test_delay_changes_apply_and_do_not_override_work(self):
        rest=Leisure(0,delays=(5,15))
        rest.set_delays((10,30),2)
        self.assertEqual(rest.deadline,12)
        rest.wake(4)
        rest.set_delays((6,25),5)
        self.assertEqual(rest.deadline,30)
        rest.set_busy(True,6)
        rest.set_delays((2,20),10)
        self.assertIsNone(rest.deadline)
        rest.set_busy(False,20)
        self.assertEqual(rest.deadline,22)

    def test_legacy_animation_users_keep_the_original_timing(self):
        rest=Leisure(0)
        self.assertTrue(180<=rest.deadline<=1800)
        rest.wake(10)
        self.assertTrue(180<=rest.deadline-10<=1800)

    def test_cancelled_tasks_do_not_keep_the_pet_awake_forever(self):
        store=FamilyStore()
        store.ingest(dict(session_id='A',event='UserPromptSubmit',turn_id='t'),100)
        store.ingest(dict(session_id='A',event='Interrupt',turn_id='t'),101)
        self.assertFalse(store.pending_work())
        self.assertFalse(store.ingest(dict(session_id='A',event='PermissionRequest',turn_id='t'),102))

    def test_invalid_habits_use_defaults_or_valid_limits(self):
        from linux.paths import habits_settings
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/'settings.json'
            path.write_text(json.dumps({'idleSleepSeconds':0,'wakeAwakeSeconds':True}))
            self.assertEqual(habits_settings(root),{'idleSleepSeconds':1,'wakeAwakeSeconds':15,'snackChancePercent':50})
            for saved, chance in ((-1,0),(101,100),(True,50),('25',50)):
                path.write_text(json.dumps({'snackChancePercent':saved}))
                self.assertEqual(habits_settings(root)['snackChancePercent'],chance)
            path.write_text('not json')
            self.assertEqual(habits_settings(root),{'idleSleepSeconds':5,'wakeAwakeSeconds':15,'snackChancePercent':50})

    def test_automatic_snack_plays_in_full_and_then_enters_sleep(self):
        clips = load_manifest(Path(__file__).resolve().parents[1]/'assets/macos-resources')
        rng = Mock()
        rng.random.return_value = .49
        rest = Leisure(0, rng=rng, delays=(5,15))
        rest.tick(4.99, True)
        rest.tick(5, False)
        rng.random.assert_not_called()
        rest.tick(6, True)
        end = 6+clips['snack'].total_duration/1000
        self.assertEqual(rest.position(clips, end-.01)[0], 'snack')
        rest.tick(end, True)
        self.assertEqual(rest.position(clips, end), ('sleep_entry', 0))
        rng.random.assert_called_once()

    def test_sleep_decision_uses_the_configured_percentage_once(self):
        for chance, draw, phase in ((0, 0, 'entering'), (50, .5, 'entering'), (100, .99, 'snacking')):
            with self.subTest(chance=chance):
                rng = Mock()
                rng.random.return_value = draw
                rest = Leisure(0, rng=rng, delays=(5,15), snack_chance=chance)
                rest.tick(5, True)
                self.assertEqual(rest.phase, phase)
                rest.cancel()
                rest.tick(6, True)
                self.assertEqual(rest.phase, 'entering')
                rng.random.assert_called_once()


if __name__=='__main__':
    unittest.main()
