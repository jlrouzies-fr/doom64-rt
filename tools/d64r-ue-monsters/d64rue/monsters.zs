// Doom 64: Unseen Evil monsters, re-authored for Retribution.
//
// The sprites and sounds are DrPyspy's (see CREDITS). The CODE here is not a
// copy of Unseen Evil's: UE's monsters descend from D64UE_MonsterBase, which
// drags in a cvar handler class, a tag system, an obituary system, a projectile
// mixin and the D64_SCALEX/Y constants. None of that belongs in Retribution --
// A_D64_Chase is A_Chase plus a Doom-64 speed multiplier that Retribution's
// monsters already have baked into their own speeds. So each actor here
// inherits from the stock Doom monster (which is also what Retribution's own
// 64* actors do) and overrides only size, sounds and the state table.
//
// SIZES. UE draws D64 sprites at YScale 0.732 in a Doom-sized world; Retribution
// draws them 1:1 and grows the hitbox to match. So the conversion is UE's box
// divided by 0.732, which reproduces Retribution's own numbers exactly: its
// zombie is 24/80, and UE's is 20/56 -> 27/76 -> 24/80.
//
// Do NOT size these off the sprite's pixel height instead. That reads plausibly
// (Retribution's CYBR is 163px tall with Height 160) but UE's sprites carry much
// more headroom than Doom's, so it puts the Revenant and the Arch-Vile at 120 --
// taller than any non-boss in the game, and they then refuse most of the spots
// the placement handler offers them.
//
// SPRITE NAMES. CPOS / SKEL / VILE / SPID / AVFR are free in Retribution -- zero
// lumps and zero RT material files. SPOS and TRCR are NOT: they carry 98 and 34
// baked _orm/_n files keyed on the bare name, so reusing them would apply
// Retribution's materials to UE's pixels and would repaint Retribution's own
// Shotgun Guy and Mother Demon ball. Those two are renamed SPO2 / TRC2 by
// tools/pack_ue_monsters.py.

// ---------------------------------------------------------------------------
// Former Sergeant -- UE's redrawn Shotgun Guy.
//
// Behaviourally identical to Retribution's 64ShotgunGuy; this is a visual
// variant, so it inherits the sounds rather than overriding them.
// ---------------------------------------------------------------------------
class D64R_FormerSergeant : ShotgunGuy
{
	Default
	{
		Radius 24;
		Height 80;
		Speed 10;            // 64ShotgunGuy's, not Doom's 8
		Decal "BulletChip";
		Tag "$TAG_D64R_SERGEANT";
	}

	States
	{
	Spawn:
		SPO2 AB 10 A_Look;
		Loop;
	See:
		SPO2 AABBCCDD 3 A_Chase;
		Loop;
	Missile:
		SPO2 E 10 A_FaceTarget;
		SPO2 F 10 BRIGHT A_SPosAttackUseAtkSound;
		SPO2 E 10;
		Goto See;
	Pain:
		SPO2 G 3;
		SPO2 G 3 A_Pain;
		Goto See;
	Death:
		SPO2 H 5;
		SPO2 I 5 A_Scream;
		SPO2 J 5 A_NoBlocking;
		SPO2 K 5;
		SPO2 L -1;
		Stop;
	XDeath:
		SPO2 M 5;
		SPO2 N 5 A_XScream;
		SPO2 O 5 A_NoBlocking;
		SPO2 PQRST 5;
		SPO2 U -1;
		Stop;
	Raise:
		SPO2 L 5;
		SPO2 KJIH 5;
		Goto See;
	}
}

// ---------------------------------------------------------------------------
// Chaingunner -- CPOS, 54x85.
// ---------------------------------------------------------------------------
class D64R_ChaingunGuy : ChaingunGuy
{
	Default
	{
		Health 70;
		Radius 24;
		Height 80;
		Speed 8;
		PainChance 170;
		Decal "BulletChip";
		SeeSound "d64r/cpos/sight";
		PainSound "d64r/cpos/pain";
		DeathSound "d64r/cpos/death";
		ActiveSound "d64r/cpos/active";
		AttackSound "weapons/chngun";
		DropItem "Chaingun";
		Tag "$TAG_D64R_CHAINGUNNER";
		Obituary "$OBIT_D64R_CHAINGUNNER";
	}

	States
	{
	Spawn:
		CPOS AB 10 A_Look;
		Loop;
	See:
		CPOS AABBCCDD 3 A_Chase;
		Loop;
	Missile:
		CPOS E 10 A_FaceTarget;
		CPOS FE 4 BRIGHT A_CPosAttack;
		CPOS F 1 A_CPosRefire;
		Goto Missile+1;
	Pain:
		CPOS G 3;
		CPOS G 3 A_Pain;
		Goto See;
	Death:
		CPOS H 5;
		CPOS I 5 A_Scream;
		CPOS J 5 A_NoBlocking;
		CPOS KLM 5;
		CPOS M -1;
		Stop;
	XDeath:
		CPOS N 5;
		CPOS O 5 A_XScream;
		CPOS P 5 A_NoBlocking;
		// CPOS stops at P. UE finishes the gib on the zombieman's frames and so
		// do we -- POSS is always present (Retribution's own), and the gibs are
		// generic meat either way.
		POSS PQRST 5;
		POSS U -1;
		Stop;
	Raise:
		CPOS M 5;
		CPOS MLKJIH 5;
		Goto See;
	}
}

// ---------------------------------------------------------------------------
// Revenant -- SKEL, 57x120. Fires UE's twin homing missiles.
// ---------------------------------------------------------------------------
class D64R_Revenant : Revenant
{
	Default
	{
		Health 300;
		Radius 24;
		Height 80;
		Mass 500;
		Speed 10;
		PainChance 100;
		MeleeThreshold 196;
		+MISSILEMORE
		SeeSound "d64r/skel/sight";
		PainSound "d64r/skel/pain";
		DeathSound "d64r/skel/death";
		ActiveSound "d64r/skel/active";
		MeleeSound "d64r/skel/melee";
		Tag "$TAG_D64R_REVENANT";
		Obituary "$OBIT_D64R_REVENANT";
		HitObituary "$OBIT_D64R_REVENANT_MELEE";
	}

	// UE fires two missiles side by side, and either BOTH seek or NEITHER does
	// (one roll, not one per missile) -- that is what makes the pair read as a
	// single volley instead of two independent shots.
	void D64R_FireVolley()
	{
		if (!target) return;

		bool doSeek = random[D64RSkel](1, 4) == 1;
		double projPitch = VectorAngle(Distance2D(target),
			(pos.z + 64) - (target.pos.z + target.height / 2));

		for (int i = 0; i < 2; i++)
		{
			double side = (i == 0) ? 12.0 : -12.0;
			let mis = D64R_RevenantMissile(A_SpawnProjectile("D64R_RevenantMissile",
				64, side, 0, CMF_AIMOFFSET | CMF_ABSOLUTEPITCH, projPitch));
			if (mis)
			{
				mis.xOff = (i == 0) ? -3 : 3;
				mis.bSEEKERMISSILE = doSeek;
			}
		}
	}

	States
	{
	Spawn:
		SKEL AB 10 A_Look;
		Loop;
	See:
		SKEL AAABBBCCCDDDEEEFFF 2 A_Chase;
		Loop;
	Melee:
		SKEL G 0 A_FaceTarget;
		SKEL G 6 A_SkelWhoosh;
		SKEL H 6 A_FaceTarget;
		SKEL I 6 A_SkelFist;
		Goto See;
	Missile:
		SKEL J 0 BRIGHT A_FaceTarget;
		SKEL J 10 BRIGHT A_FaceTarget;
		SKEL K 10 { invoker.D64R_FireVolley(); }
		SKEL K 10 A_FaceTarget;
		Goto See;
	Pain:
		SKEL L 5;
		SKEL L 5 A_Pain;
		Goto See;
	Death:
		SKEL LM 7;
		SKEL N 7 A_Scream;
		SKEL O 7 A_NoBlocking;
		SKEL P 7;
		SKEL Q -1;
		Stop;
	Raise:
		SKEL Q 5;
		SKEL PONML 5;
		Goto See;
	}
}

// Self-contained trail so the pk3 does not depend on Retribution's
// 64MotherBallTrail existing.
class D64R_RevenantTrail : RocketSmokeTrail {}

class D64R_RevenantMissile : Actor
{
	const TRACEANG = 16.875;
	double xOff;

	Default
	{
		// Half size, from play. The sprite is the same 32x24 fireball
		// Retribution uses for the Mother Demon's tracer, which reads far too
		// heavy coming from a Revenant, twice. The hitbox comes down with it:
		// leaving Doom's 11/8 under a half-size sprite means being hit by
		// visibly empty air.
		Scale 0.5;
		Radius 6;
		Height 6;
		Speed 10;
		Damage 5;
		Projectile;
		+SEEKERMISSILE
		+RANDOMIZE
		+BRIGHT
		SeeSound "d64r/skel/attack";
		DeathSound "d64r/skel/tracex";
		Decal "RevenantScorch";
		Obituary "$OBIT_D64R_REVENANT";
	}

	// Hand-rolled seek rather than A_SeekerMissile: the missile turns in fixed
	// TRACEANG steps and snaps when it is within one step, which is what gives
	// the D64 tracer its stepped arc instead of a smooth curve.
	void D64R_Seek()
	{
		if (!bSEEKERMISSILE) return;
		if (!tracer || tracer.health <= 0) return;

		double targface = AngleTo(tracer) + xOff;
		double diff = DeltaAngle(angle, targface);

		int sign = 0;
		if (diff < 0) sign = -1;
		else if (diff > 0) sign = 1;

		angle += TRACEANG * sign;
		if (AbsAngle(angle, targface) < TRACEANG) angle = targface;

		VelFromAngle();

		double dist = DistanceBySpeed(tracer, speed);
		if (dist <= 0) return;
		double slope = (tracer.pos.z + tracer.height / 2 - pos.z) / dist;
		if (slope == vel.z) return;
		vel.z += 0.125 * (slope < vel.z ? -1 : 1);
	}

	States
	{
	Spawn:
		TRC2 AB 3;
	SpawnLoop:
		TRC2 AB 3
		{
			invoker.D64R_Seek();
			A_SpawnItemEx("D64R_RevenantTrail", 0, 0, 0, 0, 0, 0, 0, SXF_NOCHECKPOSITION);
		}
		Loop;
	Death:
		TRC2 C 4 A_FadeOut(0.1);
		TRC2 D 3 A_FadeOut(0.1);
		TRC2 EF 2 A_FadeOut(0.1);
		TRC2 GHI 2;
		Stop;
	}
}

// ---------------------------------------------------------------------------
// Arch-Vile -- VILE, 59x123.
// ---------------------------------------------------------------------------
class D64R_Archvile : Archvile
{
	Default
	{
		Health 700;
		Radius 24;
		Height 80;
		Mass 500;
		Speed 15;
		PainChance 10;
		MaxTargetRange 896;
		+QUICKTORETALIATE
		+NOTARGET
		SeeSound "d64r/vile/sight";
		ActiveSound "d64r/vile/active";
		PainSound "d64r/vile/pain";
		DeathSound "d64r/vile/death";
		Tag "$TAG_D64R_ARCHVILE";
		Obituary "$OBIT_D64R_ARCHVILE";
	}

	States
	{
	Spawn:
		VILE AB 10 A_Look;
		Loop;
	See:
		VILE AAABBCCDDDEEFF 2 A_Chase("Melee", "Missile", CHF_RESURRECT);
		Loop;
	Missile:
		"----" A 0
		{
			A_StartSound("d64r/vile/attack", CHAN_VOICE);
			A_StartSound("vile/start", CHAN_WEAPON);
		}
		VILE G 10 BRIGHT A_FaceTarget;
		VILE H 8 BRIGHT A_VileTarget("D64R_ArchvileFire");
		VILE IJKLMN 8 BRIGHT A_FaceTarget;
		VILE O 8 BRIGHT A_VileAttack("d64r/vile/burn");
		VILE P 8 BRIGHT;
		VILE Q 12;
		Goto See;
	Heal:
		// UE writes "VILE Z[\" here, but there is no backslash frame in the
		// sprite set -- it ships Z (25), [ (26) and ^ (29), with 27 and 28
		// never drawn. Referencing the missing frame makes GZDoom complain at
		// load and renders nothing, so the third beat uses ^.
		VILE Z[^ 10 BRIGHT;
		Goto See;
	Pain:
		VILE R 5;
		VILE R 5 A_Pain;
		Goto See;
	Death:
		VILE S 7;
		VILE T 7 A_Scream;
		VILE U 7 A_NoBlocking;
		VILE VWX 7;
		VILE Y -1;
		Stop;
	}
}

// The flame that walks to the victim. UE drives the frame from level.maptime
// rather than from state durations so the fire animates at a constant rate no
// matter when it was spawned, and fades in over its first ~30 tics.
class D64R_ArchvileFire : ArchvileFire
{
	Default
	{
		-ZDOOMTRANS
		+BRIGHT
		// OPAQUE, not UE's "Translucent" at Alpha 0.3, and this is what makes the
		// flame light the room.
		//
		// Measured: with the Lost Soul standing in the same dark lab as a control,
		// its flame pooled orange on the floor and this one lit nothing, on the
		// SAME textures.json recipe -- emissiveMult 0.35, lightIntensity 450,
		// lightColorHEX ff9028, lightEvenOnDynamic, cloned from SKUL row for row.
		// rt_tex_probe showed the one difference: SKUL draws at color=0xFFFFFFFF
		// and this drew at 0xB7FFFFFF. 0xB7 is 0.72, which is rt_translucent_minalpha
		// exactly -- the path tracer had floored it, so UE's alpha ramp was doing
		// nothing except keeping the primitive off the opaque path.
		RenderStyle "Normal";
		Alpha 1.0;
	}

	private void D64R_JumpToTracer()
	{
		if (!tracer || !target) return;
		if (!target.CheckSight(tracer, 0)) return;

		if (tracer is "PlayerPawn")
		{
			let pawn = PlayerPawn(tracer);
			Vector3 warpPos = tracer.Vec3Angle(24, tracer.angle, 0);
			warpPos.z = pawn.player.viewz - (41 + pawn.player.crouchviewdelta);
			SetOrigin(warpPos, true);
			return;
		}
		SetOrigin(tracer.Vec3Angle(24, tracer.angle, 0), true);
	}

	override void PostBeginPlay()
	{
		super.PostBeginPlay();
		D64R_JumpToTracer();
		ClearInterpolation();
		D64R_ApplyVisibility();
	}

	// d64_ue_vilefire 0 HIDES this, it does not remove it. The flame warps onto
	// the victim every tic, so at point-blank it fills the screen and there is no
	// way to see what the Arch-Vile itself looks like while it casts. Hiding is
	// the right lever rather than not spawning it: A_VileAttack reads self.tracer
	// and calls A_Explode on it, so a missing flame would silently drop the blast
	// half of the attack and quietly change the fight.
	private void D64R_ApplyVisibility()
	{
		let cv = CVar.FindCVar("d64_ue_vilefire");
		bINVISIBLE = (cv && cv.GetInt() == 0);
	}

	override void Tick()
	{
		super.Tick();
		if (bDESTROYED) return;
		frame = ((level.maptime / 2) % 8);
		// UE's fade-in went with the translucency; see the Default block.
		D64R_ApplyVisibility();
		D64R_JumpToTracer();
	}

	States
	{
	Spawn:
		AVFR A 2 A_StartSound("vile/firestrt", CHAN_BODY);
		AVFR BCD 2;
		AVFR C 2 A_StartSound("d64r/vile/burn", CHAN_BODY);
		AVFR BCBCDCDCDEDED 2;
		AVFR E 2 A_StartSound("d64r/vile/burn", CHAN_BODY);
		AVFR FEFEFGHGHGH 2;
		Stop;
	}
}

// ---------------------------------------------------------------------------
// Spider Mastermind -- SPID, 316x143.
//
// The boss flags are deliberately cleared. Stock SpiderMastermind carries
// +BOSSDEATH, +E3M8BOSS and +E4M8BOSS, which fire a level-wide special action
// when the last one dies. This one is dropped into arbitrary Retribution maps by
// the placement handler, so leaving them on would let it end a map that was
// never designed around it.
//
// UE draws its beam with a stretched, pitched billboard driven by a per-tic
// length update (D64UE_UnmakerBolt). That machinery is tied to UE's unmaker
// weapon; here the hitscan is kept -- it is what actually deals the damage -- and
// the beam is drawn by laying Retribution's own UnmakerLaserTrail down the ray.
// ---------------------------------------------------------------------------
class D64R_SpiderMastermind : SpiderMastermind
{
	Default
	{
		Health 3000;
		// Radius 64, not the 128 both Doom and UE use, and not the ~123 that
		// Retribution's own sprite-to-hitbox ratio would suggest for a 316px
		// sprite. Measured, not guessed: at 128 it was offered all 9 free
		// Arachnotron spots on MAP22 and TestMobjLocation refused every one --
		// Doom 64's arenas are built for Retribution's roster, whose widest
		// footprint is the Mother Demon at 64. So 64 is the largest box the
		// game's geometry is actually known to accommodate. The sprite overhangs
		// it heavily, which is ordinary here: Retribution's Arachnotron is
		// already a 144px sprite on a radius-56 box.
		Radius 64;
		Height 136;
		Mass 1000;
		Speed 12;
		PainChance 40;
		-BOSSDEATH
		-E3M8BOSS
		-E4M8BOSS
		SeeSound "d64r/spid/sight";
		AttackSound "d64r/spid/attack";
		PainSound "d64r/spid/pain";
		DeathSound "d64r/spid/death";
		ActiveSound "d64r/spid/active";
		Tag "$TAG_D64R_MASTERMIND";
		Obituary "$OBIT_D64R_MASTERMIND";
	}

	void D64R_FireVolley()
	{
		for (int i = 0; i < 3; i++)
		{
			if (!target) return;

			double aoff = Random2[D64RSpid]() * (22.5 / 256);
			A_SpawnProjectile("D64R_SpiderLaser", 24, 0, aoff);
			A_StartSound("d64r/spid/laser", CHAN_WEAPON, CHANF_OVERLAP,
				pitch: frandom[D64RSpid](0.9, 1.1));
		}

		A_StartSound("d64r/spid/attack", CHAN_WEAPON);
	}

	States
	{
	Spawn:
		SPID Z 5 A_Look;
		Loop;
	See:
		SPID A 3 { A_Chase(); A_StartSound("d64r/spid/walk"); }
		SPID ABBCC 3 A_Chase;
		SPID D 3 { A_Chase(); A_StartSound("d64r/spid/walk"); }
		SPID DEEFF 3 A_Chase;
		Loop;
	Missile:
		// TIMING IS NOT UE'S. Its loop is "HG 4" then "G 1 A_SpidRefire", i.e. a
		// three-bolt volley every ~5 tics for as long as it can see you, which
		// against Doom 64's arena sizes is a wall of lasers with no gap to move
		// in. Widened to a volley roughly every 24 tics: a longer wind-up to read
		// the tell, and a real pause on the refire so there is a window between
		// bursts. Cut the 14 back toward 1 to get UE's original cadence.
		SPID G 25 BRIGHT
		{
			A_StartSound("d64r/spid/windup", CHAN_WEAPON);
			A_FaceTarget();
		}
		SPID HG 6 BRIGHT { invoker.D64R_FireVolley(); }
		SPID G 14 BRIGHT A_SpidRefire;
		Goto Missile+1;
	Pain:
		SPID G 3 A_StopSound(CHAN_WEAPON);
		SPID G 3 A_Pain;
		Goto See;
	Death:
		"----" A 0 A_StopSound(CHAN_WEAPON);
		SPID I 30 A_Scream;
		SPID J 8;
		SPID K 7;
		SPID L 6;
		SPID M 5;
		SPID N 4 A_NoBlocking;
		SPID OP 4;
		SPID QRS 4;
		SPID S -1;
		Stop;
	}
}

// The beam. UE draws its Mastermind laser as a stretched, pitched billboard whose
// length is recomputed every tic; that machinery is tied to UE's unmaker weapon.
// Retribution already solves the same problem its own way and this follows that
// instead -- UnmakerLaser is a speed-200 FastProjectile that, EVERY TIC, lays a
// dense tail of puffs behind itself at fractional-velocity offsets. That is what
// makes it read as a continuous beam.
//
// The spacing is the whole point. Retribution steps k by 0.5 with vel/35, which
// at speed 200 is a puff every ~2.9 units. An earlier version of this drew the
// beam as puffs 48 units apart along a hitscan and it read as a dotted line of
// separate points, not a beam.
//
// Shorter tail than Retribution's (k to 24 rather than 37.5, so ~43 puffs over
// ~120 units instead of 70 over ~214): the Mastermind fires THREE of these per
// volley, and the player's Unmaker only ever fires one.
class D64R_SpiderLaser : FastProjectile
{
	Default
	{
		Radius 2;
		Height 4;
		Speed 200;
		ProjectileKickBack 16;
		Projectile;
		+RANDOMIZE
		RenderStyle "Add";
		Alpha 1;
		SeeSound "";
		DeathSound "";
		Obituary "$OBIT_D64R_MASTERMIND";
		// UE's hitscan rolled random(1,5)*3 per bolt. Doom's "Damage n" would be
		// n*random(1,8) instead, so this keeps UE's spread exactly.
		DamageFunction (random[D64RSpid](1, 5) * 3);
	}

	States
	{
	Spawn:
		TNT1 A 1
		{
			for (double k = 3.0; k <= 24.0; k += 0.5)
			{
				A_SpawnItemEx("D64R_SpiderBeamPuff",
					(k * vel.x) / -35.0, -(k * vel.y) / -35.0, 2 + (k * vel.z) / -35.0,
					0, 0, 0, 0, SXF_ABSOLUTEANGLE);
			}
		}
		Loop;
	Death:
		LPUF AB 3 BRIGHT A_FadeOut(0.10);
		Loop;
	}
}

// The beam element, a restatement of Retribution's UnmakerLaserTrail rather than
// a subclass of it: that one is DECORATE, and GZDoom compiles ALL ZScript before
// it parses any DECORATE, so a ZScript class can never inherit from it. Its LPUF
// art is used as-is. It exists as a class of ours purely so GLDEFS has something
// to hang the beam light on without also lighting the player's Unmaker.
class D64R_SpiderBeamPuff : Actor
{
	Default
	{
		Radius 2;
		Height 4;
		Scale 0.65;
		Alpha 1;
		Speed 0;
		Damage 0;
		Projectile;
		+RANDOMIZE
		RenderStyle "Add";
		SeeSound "";
		DeathSound "";
	}

	States
	{
	Spawn:
		LPUF C 5 BRIGHT;
		Stop;
	Death:
		LPUF ABC 2 BRIGHT;
		Stop;
	}
}
